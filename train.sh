#!/bin/bash
# ============================================
# THU-BDC2026 训练脚本
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  THU-BDC2026 模型训练"
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

# 检查数据
if [ ! -f "data/train.csv" ]; then
    echo "错误: 未找到训练数据 data/train.csv" >&2
    exit 1
fi

# 执行训练
echo "开始训练..."
echo "----------------------------------------"
$PYTHON_BIN code/src/train.py "$@"
TRAIN_EXIT=$?

echo "----------------------------------------"
if [ $TRAIN_EXIT -eq 0 ]; then
    echo "训练完成 ✓"
    echo ""
    echo "模型保存位置:"
    ls -lh model/ 2>/dev/null || echo "  (未找到model目录)"
else
    echo "训练失败 (退出码: $TRAIN_EXIT)" >&2
    exit $TRAIN_EXIT
fi

echo "========================================"
