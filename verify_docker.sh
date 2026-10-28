#!/bin/bash
# ============================================
# THU-BDC2026 Docker镜像验证脚本
# 运行方式: bash verify_docker.sh
# ============================================

set -e

IMAGE_NAME="bdc2026:latest"
PASS_COUNT=0
FAIL_COUNT=0

check_pass() {
    echo "  ✓ $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

check_fail() {
    echo "  ✗ $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

echo "========================================"
echo "  THU-BDC2026 Docker镜像验证"
echo "========================================"
echo ""

# 1. 检查镜像是否存在
echo "[1/8] 检查镜像是否存在..."
if docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    check_pass "镜像 $IMAGE_NAME 存在"
else
    check_fail "镜像 $IMAGE_NAME 不存在，请先构建镜像"
    echo ""
    echo "验证中断：镜像不存在"
    exit 1
fi

# 2. 检查镜像大小
echo ""
echo "[2/8] 检查镜像大小..."
IMAGE_SIZE=$(docker image inspect "$IMAGE_NAME" --format "{{.Size}}")
IMAGE_SIZE_GB=$(echo "scale=2; $IMAGE_SIZE / 1024 / 1024 / 1024" | bc)
# 10GB = 10737418240 bytes
if [ "$IMAGE_SIZE" -le 10737418240 ]; then
    check_pass "镜像大小: ${IMAGE_SIZE_GB}GB (≤10GB)"
else
    check_fail "镜像大小: ${IMAGE_SIZE_GB}GB (>10GB，超出限制!)"
fi

# 3. 检查目录结构
echo ""
echo "[3/8] 检查目录结构..."
REQUIRED_DIRS="code/src data model output temp"
for dir in $REQUIRED_DIRS; do
    if docker run --rm "$IMAGE_NAME" /bin/bash -c "[ -d /app/$dir ]" 2>/dev/null; then
        check_pass "目录 /app/$dir 存在"
    else
        check_fail "目录 /app/$dir 不存在"
    fi
done

# 4. 检查入口脚本
echo ""
echo "[4/8] 检查入口脚本..."
REQUIRED_SCRIPTS="init.sh train.sh test.sh"
for script in $REQUIRED_SCRIPTS; do
    if docker run --rm "$IMAGE_NAME" /bin/bash -c "[ -x /app/$script ]" 2>/dev/null; then
        check_pass "脚本 /app/$script 存在且可执行"
    else
        check_fail "脚本 /app/$script 不存在或不可执行"
    fi
done

# 5. 检查数据文件
echo ""
echo "[5/8] 检查数据文件..."
REQUIRED_FILES="data/train.csv data/test.csv"
for file in $REQUIRED_FILES; do
    if docker run --rm "$IMAGE_NAME" /bin/bash -c "[ -f /app/$file ]" 2>/dev/null; then
        check_pass "文件 /app/$file 存在"
    else
        check_fail "文件 /app/$file 不存在"
    fi
done

# 6. 检查模型文件
echo ""
echo "[6/8] 检查模型文件..."
MODEL_DIR="model/60_158+39"
REQUIRED_MODEL_FILES="best_model.pth scaler.pkl config.json"
for file in $REQUIRED_MODEL_FILES; do
    if docker run --rm "$IMAGE_NAME" /bin/bash -c "[ -f /app/$MODEL_DIR/$file ]" 2>/dev/null; then
        check_pass "模型文件 /app/$MODEL_DIR/$file 存在"
    else
        check_fail "模型文件 /app/$MODEL_DIR/$file 不存在"
    fi
done

# 7. 运行初始化脚本
echo ""
echo "[7/8] 运行初始化脚本..."
INIT_OUTPUT=$(docker run --rm "$IMAGE_NAME" /bin/bash /app/init.sh 2>&1)
if echo "$INIT_OUTPUT" | grep -q "初始化完成"; then
    check_pass "init.sh 运行成功"
else
    check_fail "init.sh 运行失败"
    echo "  输出: $INIT_OUTPUT"
fi

# 8. 运行预测测试（验证时间限制）
echo ""
echo "[8/8] 运行预测测试（预计需要4-5分钟）..."
echo "  开始计时..."
START_TIME=$(date +%s)

# 运行预测并捕获输出
PREDICT_OUTPUT=$(docker run --rm \
    -v "$(pwd)/output:/app/output" \
    -v "$(pwd)/temp:/app/temp" \
    "$IMAGE_NAME" \
    /bin/bash /app/test.sh 2>&1) || true

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ELAPSED_MIN=$(echo "scale=1; $ELAPSED / 60" | bc)

echo "  预测耗时: ${ELAPSED}秒 (${ELAPSED_MIN}分钟)"

if [ "$ELAPSED" -le 300 ]; then
    check_pass "预测时间 ${ELAPSED_MIN}分钟 (≤5分钟)"
else
    check_fail "预测时间 ${ELAPSED_MIN}分钟 (>5分钟，超出限制!)"
fi

# 检查输出文件
if echo "$PREDICT_OUTPUT" | grep -q "预测完成"; then
    check_pass "预测脚本正常完成"
else
    check_fail "预测脚本未完成"
fi

# 验证输出格式
if docker run --rm \
    -v "$(pwd)/output:/app/output" \
    "$IMAGE_NAME" \
    /bin/bash -c "[ -f /app/output/result.csv ]" 2>/dev/null; then
    
    # 检查CSV格式
    CSV_CHECK=$(docker run --rm \
        -v "$(pwd)/output:/app/output" \
        "$IMAGE_NAME" \
        /bin/bash -c "
            head -1 /app/output/result.csv | grep -q 'stock_id,weight' && echo 'format_ok' || echo 'format_error'
        " 2>/dev/null)
    
    if [ "$CSV_CHECK" = "format_ok" ]; then
        check_pass "output/result.csv 格式正确 (stock_id,weight)"
    else
        check_fail "output/result.csv 格式不正确"
    fi
    
    # 检查股票数量
    STOCK_COUNT=$(docker run --rm \
        -v "$(pwd)/output:/app/output" \
        "$IMAGE_NAME" \
        /bin/bash -c "
            wc -l < /app/output/result.csv | tr -d ' '
        " 2>/dev/null)
    # 减1是因为第一行是表头
    STOCK_COUNT=$((STOCK_COUNT - 1))
    
    if [ "$STOCK_COUNT" -le 5 ] && [ "$STOCK_COUNT" -gt 0 ]; then
        check_pass "选股数量: $STOCK_COUNT (≤5)"
    else
        check_fail "选股数量: $STOCK_COUNT (不符合要求)"
    fi
    
else
    check_fail "output/result.csv 未生成"
fi

echo ""
echo "========================================"
echo "  验证结果总结"
echo "========================================"
echo "  通过: $PASS_COUNT"
echo "  失败: $FAIL_COUNT"
echo ""

if [ "$FAIL_COUNT" -eq 0 ]; then
    echo "  ✅ 所有验证通过！镜像符合比赛要求。"
    echo ""
    echo "  下一步可以执行打包提交:"
    echo "    docker save -o <团队名称>.tar bdc2026:latest"
else
    echo "  ⚠️  存在 $FAIL_COUNT 项验证失败，请检查并修复。"
    exit 1
fi

echo "========================================"
