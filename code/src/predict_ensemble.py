import os
import multiprocessing as mp
import json
import argparse

import numpy as np
import pandas as pd
import torch

from config import config
from factor_store import load_factor_snapshot
from factor_store import resolve_factor_pipeline
from model import StockTransformer
from portfolio.policy import scores_to_portfolio
from data_manager import collect_data_sources
from data_manager import load_stock_to_industry_map
from data_manager import build_stock_industry_index as build_stock_industry_index_from_manager
from data_manager import save_data_manifest
from data_manager import load_train_dataset_from_build_manifest
from data_manager import log_dataset_manifest_info
from utils import apply_cross_sectional_normalization
from utils import augment_engineered_features
from utils import resolve_feature_indices
from predict import preprocess_predict_data
from predict import build_inference_sequences
from predict import load_prediction_strategy
from predict import apply_optional_global_scaler
from predict import dump_predict_factor_snapshot


def load_single_model(model_dir, device, stock_ids, features, stock_industry_idx):
    model_path = os.path.join(model_dir, 'best_model.pth')
    prior_graph_path = os.path.join(model_dir, 'prior_graph_adj.npy')

    if not os.path.exists(model_path):
        raise FileNotFoundError(f'未找到模型文件: {model_path}')

    config_path = os.path.join(model_dir, 'config.json')
    model_config = config.copy()
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            saved_config = json.load(f)
        model_config.update(saved_config)

    model = StockTransformer(input_dim=len(features), config=model_config, num_stocks=len(stock_ids))
    market_context_feature_names = model_config.get(
        'market_gating_context_feature_names',
        [
            'market_median_return',
            'market_total_turnover_log',
            'market_limit_up_count_log',
            'market_limit_up_ratio',
        ],
    )
    market_context_indices = resolve_feature_indices(features, market_context_feature_names)
    model.set_market_context_feature_indices(market_context_indices)
    model.set_stock_industry_index(torch.from_numpy(stock_industry_idx))

    mask_mode = str(model_config.get('cross_stock_mask_mode', 'similarity')).lower()
    if os.path.exists(prior_graph_path):
        prior_graph = np.load(prior_graph_path)
        if prior_graph.ndim == 2 and prior_graph.shape[0] == prior_graph.shape[1] == len(stock_ids):
            model.set_prior_graph(torch.from_numpy(prior_graph.astype(np.bool_)))
            print(f'  加载先验图邻接矩阵: {prior_graph_path}')
        else:
            print(f'  先验图形状不匹配，忽略')
    elif mask_mode in {'prior', 'prior_similarity'}:
        print('  未找到先验图文件，回退为 similarity 稀疏注意力')
        model.cross_stock_attention.mask_mode = 'similarity'

    state_dict = torch.load(model_path, map_location=device)
    load_result = model.load_state_dict(state_dict, strict=False)

    multi_scale_prefixes = (
        'ultra_short_temporal_encoder.',
        'ultra_short_feature_attention.',
        'short_temporal_encoder.',
        'long_temporal_encoder.',
        'short_feature_attention.',
        'long_feature_attention.',
        'short_horizon_fusion_gate.',
        'short_horizon_norm.',
        'multi_scale_fusion_gate.',
        'multi_scale_branch_norm.',
    )
    temporal_cross_stock_prefixes = (
        'temporal_cross_stock_attention.',
    )
    compatible_prefixes = ('market_gate.', 'market_macro_proj.', 'volatility_head.') + multi_scale_prefixes
    compatible_prefixes = compatible_prefixes + temporal_cross_stock_prefixes
    compatible_exact_keys = {'multi_scale_branch_logits'}

    non_compatible_missing = [
        k for k in load_result.missing_keys
        if (k not in compatible_exact_keys) and (not k.startswith(compatible_prefixes))
    ]
    if non_compatible_missing:
        print(f'  警告: 模型参数缺失且无法兼容: {non_compatible_missing[:10]}')

    if any(k.startswith('market_gate.') for k in load_result.missing_keys):
        print('  检测到旧版checkpoint（缺少 market_gate 参数），已自动关闭 market gating')
        model.use_market_gating = False
    if any(k.startswith('market_macro_proj.') for k in load_result.missing_keys):
        print('  检测到旧版checkpoint（缺少 market macro 参数），已自动关闭宏观情绪 gate')
        model.use_market_gating_macro_context = False
    if any(k.startswith('volatility_head.') for k in load_result.missing_keys):
        print('  检测到旧版checkpoint（缺少 volatility_head 参数），已自动关闭多任务辅助头')
        model.use_multitask_volatility = False
    if any((k == 'multi_scale_branch_logits') or k.startswith(multi_scale_prefixes) for k in load_result.missing_keys):
        print('  检测到旧版checkpoint（缺少 multi-scale 参数），已自动关闭多尺度时序分支')
        model.use_multi_scale_temporal = False
    if any(k.startswith(temporal_cross_stock_prefixes) for k in load_result.missing_keys):
        print('  检测到旧版checkpoint（缺少 temporal cross-stock 参数），已自动关闭时间步级跨股交互')
        model.use_temporal_cross_stock_attention = False

    model.to(device)
    model.eval()
    return model, model_config


def predict_with_model(model, x, stock_indices, stock_valid_mask, model_config, device):
    use_tta = bool(model_config.get('use_tta', False))
    tta_num_samples = int(model_config.get('tta_num_samples', 5))
    tta_noise_std = float(model_config.get('tta_noise_std', 0.01))

    with torch.no_grad():
        if use_tta and tta_num_samples > 1:
            all_scores = []
            for i in range(tta_num_samples):
                if i == 0:
                    x_tta = x
                else:
                    noise = torch.randn_like(x) * tta_noise_std
                    x_tta = x + noise
                score_i = model(
                    x_tta,
                    stock_indices=stock_indices,
                    stock_valid_mask=stock_valid_mask,
                ).squeeze(0).detach().cpu().numpy()
                all_scores.append(score_i)
            scores = np.mean(all_scores, axis=0)
        else:
            scores = model(
                x,
                stock_indices=stock_indices,
                stock_valid_mask=stock_valid_mask,
            ).squeeze(0).detach().cpu().numpy()

    return scores


def main():
    parser = argparse.ArgumentParser(description='多模型集成预测')
    parser.add_argument('--model-dirs', nargs='+', required=True, help='模型目录列表，多个模型用空格分隔')
    parser.add_argument('--ensemble-method', type=str, default='mean', choices=['mean', 'rank_mean'],
                        help='集成方法: mean(分数平均) 或 rank_mean(排名平均)')
    parser.add_argument('--output', type=str, default='', help='输出结果文件路径')
    args = parser.parse_args()

    current_script_path = os.path.abspath(__file__)
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_script_path)))

    data_dir = os.path.join(project_dir, 'data')
    train_csv_path = os.path.join(data_dir, 'train.csv')
    output_base_dir = os.path.join(project_dir, 'output')
    os.makedirs(output_base_dir, exist_ok=True)

    primary_model_dir = args.model_dirs[0]
    config['output_dir'] = primary_model_dir

    output_path = args.output if args.output else os.path.join(output_base_dir, 'result_ensemble.csv')
    scores_output_path = os.path.join(output_base_dir, 'prediction_scores_ensemble.csv')

    print(f'集成模型数量: {len(args.model_dirs)}')
    for i, md in enumerate(args.model_dirs):
        print(f'  模型 {i+1}: {md}')
    print(f'集成方法: {args.ensemble_method}')

    data_manifest = collect_data_sources(config, include_csv_stats=True)
    manifest_path = save_data_manifest(config['output_dir'], data_manifest, filename='data_manifest_predict_ensemble.json')
    print(f'已生成预测数据源清单: {manifest_path}')

    factor_snapshot_path = os.path.join(primary_model_dir, 'active_factors.json')
    effective_features_path = os.path.join(primary_model_dir, 'effective_features.json')
    scaler_path = os.path.join(primary_model_dir, 'scaler.pkl')
    industry_index_path = os.path.join(primary_model_dir, 'stock_industry_idx.npy')

    if os.path.exists(factor_snapshot_path):
        feature_pipeline = load_factor_snapshot(factor_snapshot_path)
        print(f'加载训练因子快照: {factor_snapshot_path}')
    else:
        feature_pipeline = resolve_factor_pipeline(
            config['feature_num'],
            config['factor_store_path'],
            config['builtin_factor_registry_path'],
        )
        print(f'未找到训练因子快照，回退到当前因子配置')

    dataset_manifest_train_path, dataset_manifest_info = load_train_dataset_from_build_manifest(config, feature_pipeline)
    log_dataset_manifest_info(dataset_manifest_info, label='predict_ensemble')

    if os.path.exists(train_csv_path):
        print(f'预测输入数据文件: {train_csv_path}')
        raw_df = pd.read_csv(train_csv_path, dtype={'股票代码': str})
    else:
        raise FileNotFoundError(f'未找到数据文件: {train_csv_path}')

    raw_df['股票代码'] = raw_df['股票代码'].astype(str).str.zfill(6)
    raw_df['日期'] = pd.to_datetime(raw_df['日期'])
    latest_date = raw_df['日期'].max()

    stock_ids = sorted(raw_df['股票代码'].unique())
    stockid2idx = {sid: idx for idx, sid in enumerate(stock_ids)}

    stock_industry_idx = None
    if os.path.exists(industry_index_path):
        try:
            cached_index = np.load(industry_index_path)
            if cached_index.ndim == 1 and cached_index.shape[0] == len(stock_ids):
                stock_industry_idx = cached_index.astype(np.int64)
                print(f'加载行业索引映射: {industry_index_path}')
            else:
                print(f'行业索引映射形状不匹配，回退重建')
        except Exception as exc:
            print(f'读取行业索引映射失败，回退重建: {exc}')
    if stock_industry_idx is None:
        stock_to_industry = load_stock_to_industry_map(
            config,
            stock_col_key='prior_graph_stock_col',
            industry_col_key='prior_graph_industry_col',
        )
        stock_industry_idx, industry_vocab, matched = build_stock_industry_index_from_manager(
            stock_ids,
            stock_to_industry,
        )
        if matched > 0:
            coverage = matched / float(max(1, len(stock_ids)))
            print(f'重建行业索引映射: stocks={len(stock_ids)}, matched={matched}, coverage={coverage:.2%}')

    processed, features = preprocess_predict_data(raw_df, stockid2idx, feature_pipeline)

    if os.path.exists(effective_features_path):
        with open(effective_features_path, 'r', encoding='utf-8') as f:
            saved_features = json.load(f)
        if isinstance(saved_features, list) and saved_features:
            missing_features = [name for name in saved_features if name not in processed.columns]
            if not missing_features:
                features = saved_features
                print(f'加载训练特征清单: {effective_features_path} | 特征数: {len(features)}')

    processed[features] = processed[features].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    processed = apply_optional_global_scaler(processed, features, scaler_path)
    dump_predict_factor_snapshot(processed, features, config['output_dir'], latest_date)

    sequence_length = config['sequence_length']
    sequences_np, sequence_stock_ids = build_inference_sequences(
        processed,
        features,
        sequence_length,
        stock_ids,
        latest_date,
    )

    if torch.cuda.is_available():
        device = torch.device('cuda')
    elif torch.backends.mps.is_available():
        device = torch.device('mps')
    else:
        device = torch.device('cpu')

    print(f'使用设备: {device}')

    x = torch.from_numpy(sequences_np).unsqueeze(0).to(device)
    stock_indices = torch.tensor(
        [[stockid2idx[sid] for sid in sequence_stock_ids]],
        dtype=torch.long,
        device=device,
    )
    stock_valid_mask = torch.ones_like(stock_indices, dtype=torch.bool, device=device)

    all_model_scores = []
    for i, model_dir in enumerate(args.model_dirs):
        print(f'\n加载模型 {i+1}/{len(args.model_dirs)}: {model_dir}')
        try:
            model, model_config = load_single_model(model_dir, device, stock_ids, features, stock_industry_idx)
            scores = predict_with_model(model, x, stock_indices, stock_valid_mask, model_config, device)
            all_model_scores.append(scores)
            print(f'  预测完成，分数范围: [{scores.min():.4f}, {scores.max():.4f}]')
        except Exception as e:
            print(f'  模型加载或预测失败: {e}')
            continue

    if not all_model_scores:
        raise RuntimeError('所有模型都预测失败')

    print(f'\n成功预测模型数: {len(all_model_scores)}')

    if args.ensemble_method == 'mean':
        ensemble_scores = np.mean(all_model_scores, axis=0)
    elif args.ensemble_method == 'rank_mean':
        all_ranks = []
        for scores in all_model_scores:
            rank = pd.Series(scores).rank(ascending=False).values
            all_ranks.append(rank)
        avg_rank = np.mean(all_ranks, axis=0)
        ensemble_scores = -avg_rank
    else:
        raise ValueError(f'不支持的集成方法: {args.ensemble_method}')

    score_df = pd.DataFrame({
        'stock_id': sequence_stock_ids,
        'score': ensemble_scores,
    }).sort_values('score', ascending=False).reset_index(drop=True)

    os.makedirs(os.path.dirname(scores_output_path) or '.', exist_ok=True)
    score_df.to_csv(scores_output_path, index=False)

    strategy = load_prediction_strategy(primary_model_dir)
    selected_ids, weights = scores_to_portfolio(ensemble_scores, sequence_stock_ids, strategy)

    output_df = pd.DataFrame({
        'stock_id': selected_ids,
        'weight': weights,
    })
    output_df.to_csv(output_path, index=False)

    print(f'\n预测日期: {latest_date.date()}')
    print(f'参与排序股票数: {len(sequence_stock_ids)}')
    print(f'全量分数已写入: {scores_output_path}')
    print(f'使用持仓策略: {strategy["name"]}')
    print(f'集成结果已写入: {output_path}')
    print(f'\nTop 10 股票:')
    for i in range(min(10, len(score_df))):
        print(f'  {i+1}. {score_df.iloc[i]["stock_id"]}: {score_df.iloc[i]["score"]:.4f}')


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
