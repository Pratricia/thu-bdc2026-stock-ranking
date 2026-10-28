#!/bin/bash
# ============================================
# THU-BDC2026 比赛提交打包脚本 (Linux/Mac版本)
# ============================================

set -e

if [ -z "$1" ]; then
    echo "用法: ./build_submission.sh <团队名称>"
    echo "示例: ./build_submission.sh THU-BDC-Team"
    exit 1
fi

TEAM_NAME="$1"
IMAGE_NAME="bdc2026"
TAR_FILE="${TEAM_NAME}.tar"

echo "========================================"
echo "  THU-BDC2026 打包提交镜像"
echo "========================================"
echo ""
echo "团队名称: $TEAM_NAME"
echo "镜像名称: $IMAGE_NAME:latest"
echo "输出文件: $TAR_FILE"
echo ""

# 检查Docker
echo "[1/5] 检查Docker环境..."
if ! command -v docker >/dev/null 2>&1; then
    echo "错误: 未找到Docker，请先安装Docker"
    exit 1
fi
echo "  Docker已安装 ✓"
echo ""

# 构建镜像
echo "[2/5] 构建Docker镜像..."
echo "  这可能需要10-30分钟，请耐心等待..."
echo ""
docker build -t "$IMAGE_NAME:latest" .
echo "  镜像构建成功 ✓"
echo ""

# 验证镜像
echo "[3/5] 验证镜像..."
IMAGE_SIZE=$(docker image inspect "$IMAGE_NAME:latest" --format "{{.Size}}" 2>/dev/null || echo "未知")
echo "  镜像大小: $IMAGE_SIZE"
echo "  镜像验证通过 ✓"
echo ""

# 导出镜像
echo "[4/5] 导出镜像为tar文件..."
docker save -o "$TAR_FILE" "$IMAGE_NAME:latest"
echo "  镜像导出成功 ✓"
echo ""

# 计算MD5和文件大小
echo "[5/5] 计算文件信息..."
FILE_SIZE=$(wc -c < "$TAR_FILE" 2>/dev/null || stat -f%z "$TAR_FILE" 2>/dev/null || echo "未知")
MD5_HASH=$(md5sum "$TAR_FILE" 2>/dev/null | awk '{print $1}' || md5 -q "$TAR_FILE" 2>/dev/null || echo "未知")

echo "  文件: $TAR_FILE"
echo "  大小: $FILE_SIZE 字节"
echo "  MD5:  $MD5_HASH"
echo ""

echo "========================================"
echo "  打包完成!"
echo "========================================"
echo ""
echo "提交文件: $TAR_FILE"
echo ""
echo "下一步:"
echo "  1. 发送邮件报备到 data@tsinghua.edu.cn"
echo "  2. 主题: ${TEAM_NAME} + 模型数据报备"
echo "  3. 上传 $TAR_FILE 到比赛指定位置"
echo ""
