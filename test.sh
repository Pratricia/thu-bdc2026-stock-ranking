#!/bin/bash
# ============================================
# THU-BDC2026 测试/预测脚本
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  THU-BDC2026 模型预测"
echo "========================================"

# 查找Python
PYTHON_BIN=$(command -v python3 || command -v python)
if [ -z "$PYTHON_BIN" ]; then
    echo "错误: 未找到Python解释器" >&2
    exit 1
fi

echo "Python: $($PYTHON_BIN --version 2>&1)"
echo "工作目录: $(pwd)"
echo ""

# 检查数据（predict.py 实际读取 data/train.csv）
if [ ! -f "data/train.csv" ]; then
    echo "错误: 未找到预测数据 data/train.csv" >&2
    exit 1
fi

# 检查模型
MODEL_DIR="model/60_158+39"
if [ ! -f "$MODEL_DIR/best_model.pth" ]; then
    echo "错误: 未找到模型权重 $MODEL_DIR/best_model.pth" >&2
    echo "请先运行 train.sh 训练模型" >&2
    exit 1
fi

# 确保输出目录存在
mkdir -p output

# 执行预测
echo "开始预测..."
echo "----------------------------------------"
START_TIME=$(date +%s)

$PYTHON_BIN code/src/test.py "$@"
PREDICT_EXIT=$?

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo "----------------------------------------"
if [ $PREDICT_EXIT -eq 0 ]; then
    echo "预测完成 ✓"
    echo "耗时: ${ELAPSED}秒"
    echo ""
    echo "结果文件:"
    if [ -f "output/result.csv" ]; then
        echo "  output/result.csv ($(wc -c < output/result.csv)字节)"
        echo ""
        echo "选股结果:"
        cat output/result.csv
    else
        echo "  警告: 未找到 output/result.csv"
    fi
else
    echo "预测失败 (退出码: $PREDICT_EXIT)" >&2
    exit $PREDICT_EXIT
fi

echo "========================================"
