#!/bin/bash
# ============================================
# THU-BDC2026 初始化脚本
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  THU-BDC2026 初始化环境"
echo "========================================"

# 检查Python
PYTHON_BIN=$(command -v python3 || command -v python)
if [ -z "$PYTHON_BIN" ]; then
    echo "错误: 未找到Python解释器" >&2
    exit 1
fi
echo "Python: $($PYTHON_BIN --version 2>&1)"

# 检查PyTorch
echo ""
echo "检查PyTorch..."
$PYTHON_BIN -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA可用: {torch.cuda.is_available()}'); print(f'CUDA版本: {torch.version.cuda if torch.cuda.is_available() else \"N/A\"}')" 2>&1 || echo "警告: PyTorch导入失败"

# 检查TA-Lib
echo ""
echo "检查TA-Lib..."
$PYTHON_BIN -c "import talib; print(f'TA-Lib: {talib.__version__}')" 2>&1 || echo "警告: TA-Lib导入失败"

# 创建必要目录
echo ""
echo "创建目录..."
mkdir -p output
mkdir -p temp
mkdir -p model
echo "output/: $(ls -d output 2>/dev/null && echo '已创建' || echo '失败')"
echo "temp/: $(ls -d temp 2>/dev/null && echo '已创建' || echo '失败')"
echo "model/: $(ls -d model 2>/dev/null && echo '已创建' || echo '失败')"

# 检查数据
echo ""
echo "检查数据文件..."
for f in data/train.csv data/test.csv; do
    if [ -f "$f" ]; then
        size=$(wc -c < "$f" 2>/dev/null || echo "0")
        echo "  $f: 存在 (${size}字节)"
    else
        echo "  $f: 未找到" >&2
    fi
done

# 检查模型
echo ""
echo "检查模型文件..."
MODEL_DIR="model/60_158+39"
if [ -f "$MODEL_DIR/best_model.pth" ]; then
    echo "  模型权重: 存在"
else
    echo "  模型权重: 未找到 (需要先训练)"
fi

echo ""
echo "========================================"
echo "  初始化完成"
echo "========================================"
