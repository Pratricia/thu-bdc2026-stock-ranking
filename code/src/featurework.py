"""
特征工程模块
============

负责从原始行情数据中计算技术指标和Alpha因子，供模型训练和推理使用。

主要功能：
- 39个技术指标特征（TA-Lib）
- 158个Alpha类因子
- 158+39合并特征集
- 数据扩增（特征噪声注入）
- 截面标准化
"""

import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import (
    engineer_features_39,
    engineer_features_158plus39,
    apply_cross_sectional_normalization,
    augment_engineered_features,
)
from factor_store import (
    resolve_factor_pipeline,
    apply_factor_expressions,
    engineer_group_features,
    load_factor_snapshot,
    save_factor_snapshot,
)
from config import config


def build_feature_pipeline(feature_set='158+39', factor_store_path=None):
    """构建特征工程流水线配置
    
    Args:
        feature_set: 特征集类型，'39' / '158+39'
        factor_store_path: 因子存储配置文件路径
    
    Returns:
        特征流水线配置字典
    """
    if factor_store_path is None:
        factor_store_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'config',
            'builtin_factors.json'
        )
    
    pipeline = resolve_factor_pipeline(
        feature_set=feature_set,
        factor_store_path=factor_store_path,
    )
    return pipeline


def engineer_features_for_stock(df, feature_set='158+39'):
    """对单只股票数据进行特征工程
    
    Args:
        df: 单只股票的行情数据DataFrame
        feature_set: 特征集类型
    
    Returns:
        包含特征的DataFrame
    """
    if feature_set == '39':
        return engineer_features_39(df)
    elif feature_set == '158+39':
        return engineer_features_158plus39(df)
    else:
        raise ValueError(f"未知的特征集类型: {feature_set}")


def apply_cross_section_norm(df, feature_cols, method='zscore', clip_value=4.0):
    """按日期截面标准化特征
    
    Args:
        df: 包含多只股票单日数据的DataFrame
        feature_cols: 要标准化的特征列名列表
        method: 标准化方法，'zscore' 或 'rank'
        clip_value: 截断值
    
    Returns:
        标准化后的DataFrame
    """
    return apply_cross_sectional_normalization(
        df=df,
        feature_cols=feature_cols,
        method=method,
        clip_value=clip_value,
    )


def add_feature_noise(df, feature_cols, noise_std=0.015):
    """给特征添加噪声（数据扩增）
    
    Args:
        df: 特征数据DataFrame
        feature_cols: 特征列名列表
        noise_std: 噪声标准差
    
    Returns:
        添加噪声后的DataFrame
    """
    result = df.copy()
    for col in feature_cols:
        if col in result.columns:
            noise = np.random.normal(0, noise_std, size=len(result))
            result[col] = result[col] + noise
    return result


if __name__ == '__main__':
    print("特征工程模块 - featurework.py")
    print(f"支持的特征集: 39, 158+39")
    print(f"默认使用: {config.get('feature_num', '158+39')}")
