# 代码说明

## 仓库内容说明

本仓库包含**完整源码 + 最终模型权重**，克隆后只差数据即可直接推理。

**已包含**：全部代码、配置、`model/60_158+39/` 推理权重（1.4 MB）。

**未包含**（单文件超过 GitHub 100 MB 上限，放在 Release 附件）：

| 内容 | 打包形式 | 获取方式 |
|---|---|---|
| `data/` 训练测试数据（476 MB） | `thu-bdc2026-data.tar.gz`（146 MB） | 从 [v1.0.0 Release](https://github.com/Pratricia/thu-bdc2026-stock-ranking/releases/tag/v1.0.0) 下载，解压到项目根目录 |
| 提交用 Docker 镜像 | `thu-bdc2026-image.tar.gz`（682 MB） | 同上，`docker load -i` 后可直接运行 |

`model/*/factor_artifacts/`（因子快照 CSV，单个 90~260 MB）、`model/*/log/`（TensorBoard 日志）和各实验副本也未入库，需要时运行 `bash train.sh` 自动重新生成。

### 快速开始

```bash
# 1. 克隆（已含模型权重）
git clone https://github.com/Pratricia/thu-bdc2026-stock-ranking.git
cd thu-bdc2026-stock-ranking

# 2. 下载并解压数据
#    从 Release 页面下载 thu-bdc2026-data.tar.gz 后放到项目根目录
tar -xzf thu-bdc2026-data.tar.gz

# 3. 安装依赖并推理
python -m pip install -r requirements.txt
bash test.sh          # 输出 output/result.csv
```

> 数据也可以自行重建：`python get_stock_data.py` 通过 baostock 公开 API 拉取行情，再运行 `data/split_train_test.py` 按日期拆分。

训练与推理的默认路径见 `code/src/config.py` 中的 `data_path` / `output_dir`，均相对项目根目录。

## 环境配置

- **Python版本**: 3.12
- **PyTorch版本**: 2.x
- **主要依赖**:
  - torch (深度学习框架)
  - pandas, numpy (数据处理)
  - TA-Lib (技术指标计算)
  - scikit-learn (标准化)
  - joblib (模型持久化)
  - tensorboardX (训练可视化)

## 数据

使用**baostock开源证券数据平台**（http://baostock.com）提供的沪深300成分股历史行情数据。baostock是一个免费、开源的证券数据平台，所有数据均可免费公开下载使用。

**数据获取方式**：通过baostock Python SDK调用公开API获取
- 开源链接：http://baostock.com
- 使用说明：详见 `get_stock_data_illustration.txt`
- 原始数据文件：stock_data.csv（MD5: A1261FE6B9C83073AE93F78A0E5B03ED）
- 训练数据：`data/train.csv`（MD5: 320EB22971C7E40C021D13E29E72B8DC），由 stock_data.csv 按日期拆分生成（`data/split_train_test.py`，因子在训练时实时计算）
- 测试数据：`data/test.csv`（MD5: EFD95E2C7E8D9362B13D088DD156E016），同上，取训练区间之后的一段日期

数据时间范围：2015年至2026年，采用后复权方式处理
包含以下字段：
- 股票代码、日期、开盘、收盘、最高、最低
- 成交量、成交额、换手率、涨跌幅等

## 预训练模型

本项目不使用外部预训练模型，所有模型均通过比赛提供的训练数据从零训练获得。

训练得到的模型文件存储于 `model/60_158+39/` 目录，主要包括：
- `best_model.pth`: 最优模型权重
- `scaler.pkl`: 特征标准化器
- `config.json`: 训练配置快照
- `active_factors.json`: 训练使用的因子快照

## 算法

### 整体思路介绍

本项目采用**排序学习（Learning to Rank）**框架进行股票选股，核心思路是：

1. **问题建模**：将每日选股问题转化为排序问题，模型输出每只股票的未来5日收益排序分数
2. **特征工程**：构建158个Alpha因子 + 39个技术指标，共197维特征
3. **模型架构**：使用 StockTransformer 模型，同时建模单股票时序模式与股票间交互关系
4. **损失函数**：组合 ListNet + Pairwise RankNet + LambdaNDCG + IC正则的多目标排序损失
5. **后处理策略**：模型打分 + 三因子（动量+换手率）百分位重排的组合选股策略
6. **输出结果**：按 `model/60_158+39/best_strategy.json` 中的策略输出，最终配置为 `softmax_top3`（前 3 只，温度 τ=0.6 的 Softmax 加权，权重和为 1）

### 方法的创新点

1. **多尺度时序编码**：同时编码超短期（1–3 日）、短期（5–10 日）、中期（20–60 日）三个尺度，并保留一路全序列基础分支，四路结果用**可学习门控**加权融合，而不是简单拼接或固定权重

2. **两处股票间交互注意力**：时序编码**之前**先做逐时间步的截面注意力（4 头，相似度 Top-30），让每只股票在每个交易日的表示就包含同日其他股票的信息；时序编码**之后**再做一次截面注意力（2 头），这一次叠加行业先验图 + 收益相关性先验图，并引入行业虚拟股 token

3. **市场状态门控**：把当日全市场的截面均值/标准差和 4 个宏观指标（涨跌幅中位数、成交额、涨停数量等）编码成 197 维门控向量，以 ±50% 的残差幅度逐特征缩放输入，实现按市场状态动态调权

4. **混合排序损失**：组合 ListNet、Pairwise RankNet、LambdaNDCG 和 IC 正则化，从多个角度优化排序质量，特别关注 Top-K 选股效果

5. **数据扩增策略**：训练时使用特征噪声注入和时间轴随机裁剪，提升模型泛化能力

6. **测试时增强（TTA）**：预测时对输入添加多次噪声取平均，进一步提升稳定性

7. **三因子后处理重排**：利用 f_ret_5d（5日动量）、f_ret_1d（1日动量）、换手率三个经典因子，通过排名百分位组合方式对模型Top200候选股进行二次排序，有效提升选股收益率

### 网络结构

模型输入为 `[N_stocks, 60, 197]`（股票数 × 60 个交易日 × 197 维特征）。注意本模型**不使用卷积**，多尺度是通过"截取不同长度的子序列 + 注意力池化"实现的。

1. **市场状态门控（输入层）**
   - 对每个特征取当日全部股票的截面均值与标准差，相加得到 197 维市场状态向量
   - 另取 4 个宏观指标（`market_median_return`、`market_total_turnover_log`、`market_limit_up_count_log`、`market_limit_up_ratio`），经 `Linear(4→64)` 投影后按 0.3 权重叠加到市场状态上
   - 再过 `LayerNorm → Linear(197→128) → GELU → Linear(128→197) → Sigmoid` 得到逐特征门控
   - 残差式缩放：`x = x * (0.5 + 0.5 * gate)`，即门控只在 ±50% 范围内调节，不会把某个特征完全关闭

2. **多尺度时序分支**（4 个分支结构相同、参数独立）
   - 窗口配置：基础分支 = 全 60 日；超短期 `[1, 2, 3]`；短期 `[5, 10]`；中期 `[20, 40, 60]`
   - 每个分支：截取最后 `max(window)` 日 → `Linear(197→64)` → **逐时间步的股票间注意力**（4 头，按特征相似度 Top-30 稀疏化）→ 正弦位置编码 → 单层 `TransformerEncoderLayer(d_model=64, nhead=2, dim_feedforward=128)`
   - 池化：`FeatureAttention` 对时间维做注意力加权；多窗口分支则对编码结果末尾 `w` 天分别池化，再对多个 `w` 的结果取均值
   - 融合：超短期与短期先做二路门控加权 + 残差 LayerNorm，再与中期分支做三路 softmax 门控加权 + 残差 LayerNorm

3. **截面交互层**
   - `CrossStockAttention`（2 头）在所有股票之间做注意力
   - 稀疏掩码由两种先验取交集：行业归属图 + 基于 `label_raw` 的收益相关性图（阈值 0.2、Top-20），并限制在特征相似度 Top-40 内
   - 行业虚拟股：为每个行业额外构造一个 token 一起参与注意力，聚合行业内信息后再回写

4. **排序输出层**
   - `ranking_layers`：`Linear(64→64) → LN → ReLU → Dropout → Linear(64→32) → LN → ReLU → Dropout`
   - `score_head`：`Linear(32→16) → ReLU → Dropout → Linear(16→1)`，输出**无界**排序分数（没有 Sigmoid，只在损失函数里按截面归一化）
   - `volatility_head`：同结构，预测未来 5 日波动率，仅训练时作为辅助任务，不参与选股

### 损失函数

采用多目标组合损失函数 `PortfolioOptimizationLoss`：

```
总损失 = listnet_weight * ListNet损失
        + pairwise_weight * Pairwise RankNet损失
        + lambda_ndcg_weight * LambdaNDCG损失
        + ic_weight * IC正则损失
        + volatility_loss_weight * 波动率预测损失（辅助任务）
```

各组件说明：

1. **ListNet损失**：基于概率分布的Listwise排序损失，学习整个排序列表的概率分布
2. **Pairwise RankNet损失**：Pairwise排序损失，优化股票对的相对顺序，关注Top 10%的股票
3. **LambdaNDCG损失**：直接优化NDCG指标，特别关注Top-K排序质量（K=40）
4. **IC正则**：Spearman秩相关系数约束，提升预测分数与真实收益的单调性
5. **波动率辅助任务**：预测未来波动率，多任务学习提升特征表示质量

损失函数参数：
- `listnet_weight`: 0.8
- `pairwise_weight`: 0.5
- `lambda_ndcg_weight`: 5.0
- `ic_weight`: 0.4
- `volatility_loss_weight`: 0.2

### 数据扩增

训练阶段使用以下数据扩增策略：

1. **特征噪声注入**
   - 以0.7的概率对特征添加高斯噪声
   - 噪声标准差：0.03
   - 作用：提升模型鲁棒性，防止过拟合

2. **时间轴随机裁剪**
   - 随机裁剪序列长度，保留比例下限：0.7
   - 作用：增强模型对不同长度历史数据的适应性

3. **标签处理**
   - 市场中性化：减去截面均值（cross_sectional_mean）
   - MAD去极值：5倍MAD截断
   - 截面标准化：z-score标准化（仅用于损失计算）

### 模型集成

本项目采用以下集成策略提升泛化能力：

1. **EMA（指数移动平均）**
   - 衰减率：0.9995
   - 从第5个epoch开始更新
   - 作用：平滑模型参数，提升测试稳定性

2. **SWA（随机权重平均）**
   - 起始epoch：25
   - 退火周期：5个epoch
   - 学习率比例：0.1
   - 作用：平均多个收敛点的权重，提升泛化性能

3. **TTA（测试时增强）**
   - 预测时对输入添加5次不同的高斯噪声
   - 噪声标准差：0.015
   - 取5次预测的平均值作为最终结果
   - 作用：降低预测方差，提升稳定性

4. **后处理三因子组合**
   - 模型Top200候选股 + 三因子百分位重排
   - 因子：f_ret_5d（5日动量）、f_ret_1d（1日动量）、换手率
   - 权重：[0.35, 0.25, 0.40]
   - 模型权重 alpha：0.25（模型分数占25%，因子组合占75%）
   - 使用排名百分位而非原始值，提升稳健性

### 算法的其他细节

1. **优化器**：AdamW
   - 学习率：4e-6
   - 权重衰减：3e-4
   - 梯度裁剪：最大范数5.0

2. **学习率调度**：余弦退火 + 预热
   - 预热epoch：6
   - 最小学习率比例：0.15

3. **正则化**
   - Dropout：0.3
   - Attention Dropout：0.25
   - Drop Path：0.2
   - 标签平滑：0.12

4. **早停机制**
   - 监控指标：rank_ic_mean（秩相关系数均值）
   - 耐心值：10个epoch
   - 最小改善：1e-5

5. **训练配置**
   - 序列长度：60个交易日
   - Batch Size：4
   - 训练轮数：50（早停可能提前结束）
   - 每epoch最大batch数：100（加速训练）
   - 混合精度训练（AMP）：开启

## 训练流程

训练脚本：`code/src/train.py`

训练流程步骤：

1. **设置随机种子**：固定 seed=42，确保可复现
2. **加载配置**：从 `config.py` 读取所有超参数
3. **数据加载**：读取 `data/train.csv` 原始行情数据
4. **数据预处理**
   - 股票代码标准化（6位补零）
   - 日期格式转换
   - 按股票分组
5. **特征工程**
   - 计算158个Alpha因子 + 39个技术指标
   - 截面特征计算（行业相对强弱、截面排名等）
   - 市场情绪特征计算
6. **标签构建**
   - 未来5日开盘价收益率
   - 市场中性化处理
   - MAD去极值
7. **数据集构建**
   - 按日期组织排序样本
   - Padding处理不同股票数量
   - 滚动验证集划分（6个fold）
8. **模型初始化**：StockTransformer
9. **训练循环**
   - 前向传播计算损失
   - 反向传播更新参数
   - EMA参数更新
   - 验证集评估
   - 早停检查
   - SWA权重收集
10. **模型保存**
    - 最优模型权重（best_model.pth）
    - 特征标准化器（scaler.pkl）
    - 配置快照（config.json）
    - 因子快照（active_factors.json）
    - 行业索引映射

## 推理流程

推理脚本：`code/src/test.py`（调用 `predict.py` 主逻辑）

推理流程步骤：

1. **设置随机种子**：固定 seed=42，确保可复现
2. **加载模型**：从 `model/60_158+39/` 加载训练好的模型和标准化器
3. **数据加载**：读取历史行情数据（用于构建60日序列）
4. **特征工程**：与训练完全一致的特征计算流程
5. **特征标准化**：使用训练时的scaler进行标准化
6. **构建推理序列**：取最近60个交易日数据
7. **TTA预测**
   - 对输入添加5次高斯噪声
   - 分别进行模型前向传播
   - 取5次预测的平均值
8. **后处理重排**
   - 取模型分数Top 200作为候选池
   - 计算三因子（f_ret_5d, f_ret_1d, 换手率）的排名百分位
   - 按权重组合模型分数和因子分数
   - 最终排序按 `best_strategy.json` 选出 Top K（当前为 Top 3）
9. **输出结果**
   - `output/result.csv`：最终选股结果（stock_id, weight）
   - `output/prediction_scores.csv`：所有股票的预测分数

## 其他注意事项

### 验证数据的划分

- 采用**滚动验证（Rolling Validation）**方式，模拟真实的时间序列预测场景
- 训练集：历史数据，验证集：训练结束后的连续一段时间
- 验证窗口大小：25 个交易日（`rolling_val_window_size=25`），步长 10 个交易日
- 验证fold数量：6个，覆盖不同市场环境
- 不使用未来数据：严格按照时间顺序划分，避免数据泄露

### 可复现性保证

- 固定随机种子（Python, NumPy, PyTorch, CUDA）
- 关闭CuDNN的benchmark模式
- 启用确定性算法
- 保存训练配置快照和因子快照
- 预测时同样固定随机种子

### 性能指标

- 主要监控指标：RankIC（秩相关系数）均值
- 辅助指标：策略收益率、夏普比率、胜率
- 早停依据：验证集RankIC均值

### 选股策略

- 选股数量与权重方式由 `model/60_158+39/best_strategy.json` 决定，最终模型选用 `softmax_top3`：**前 3 只，温度 τ=0.6 的 Softmax 加权**
- 若该文件缺失，`predict.py` 会回退到默认的 `equal_top5`（前 5 只等权）
- 后处理：模型Top200 + 三因子百分位重排
