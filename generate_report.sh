#!/bin/bash
# ==============================================================================
# 邮件报备信息生成脚本
# 使用方法: ./generate_report.sh <团队名称>
# ==============================================================================

set -e

if [ -z "$1" ]; then
    echo "用法: $0 <团队名称>"
    echo "示例: $0 THU-BDC-Team"
    exit 1
fi

TEAM_NAME="$1"

echo "============================================"
echo "邮件报备信息"
echo "团队名称: $TEAM_NAME"
echo "============================================"

echo -e "\n【邮件主题】"
echo "${TEAM_NAME} + 模型数据报备"

echo -e "\n【邮件内容】"
echo "尊敬的比赛组委会："
echo ""
echo "本团队提交的参赛项目信息如下："
echo ""
echo "一、开源数据集使用情况"
echo "1. 比赛官方提供的沪深300成分股历史行情数据"
echo "   - 来源：比赛官方提供"
echo "   - 文件：data/train.csv, data/test.csv"
echo ""
echo "二、开源技术指标库"
echo "1. TA-Lib（技术分析库）"
echo "   - 来源：http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz"
echo "   - MD5：待计算"
echo "   - 使用方式：用于计算39个技术指标特征"
echo ""
echo "三、预训练模型使用情况"
echo "本项目未使用任何外部预训练模型，所有模型均通过比赛提供的数据从零训练获得。"
echo ""
echo "四、提交文件信息"
echo "待打包完成后补充："
echo "- Docker镜像文件名：${TEAM_NAME}.tar"
echo "- 文件大小：待计算"
echo "- MD5值：待计算"
echo ""
echo "五、可复现性说明"
echo "1. 固定随机种子：42"
echo "2. 在固定种子下，训练和预测结果完全一致"
echo "3. 训练和预测均不依赖网络连接"
echo ""
echo "此致"
echo "敬礼"
echo "${TEAM_NAME}"
echo "2026年7月"

echo -e "\n【收件邮箱】"
echo "data@tsinghua.edu.cn"

echo -e "\n【注意事项】"
echo "1. 邮件报备截止日期：2026年7月18日"
echo "2. 邮件中请勿直接上传文件，仅提供链接和MD5值"
echo "3. 报备后不得更改开源模型和数据"
