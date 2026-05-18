#!/bin/bash

# =============================================================================
# Gitee 部署脚本
# 用法: ./deploy-to-gitee.sh [gitee仓库URL] [分支名]
# 示例: ./deploy-to-gitee.sh https://gitee.com/username/weibo-monitor.git main
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认配置
GITEE_URL="${1:-}"
BRANCH="${2:-main}"
REMOTE_NAME="gitee"

echo -e "${YELLOW}=== Gitee 部署脚本 ===${NC}"

# 检查是否提供了 Gitee URL
if [ -z "$GITEE_URL" ]; then
    echo -e "${RED}错误: 请提供 Gitee 仓库 URL${NC}"
    echo "用法: ./deploy-to-gitee.sh <gitee仓库URL> [分支名]"
    echo "示例: ./deploy-to-gitee.sh https://gitee.com/username/weibo-monitor.git"
    exit 1
fi

# 检查 git 仓库
if [ ! -d ".git" ]; then
    echo -e "${RED}错误: 当前目录不是 git 仓库${NC}"
    exit 1
fi

# 检查远程仓库是否已存在
echo -e "${YELLOW}检查 Gitee remote 配置...${NC}"
if git remote | grep -q "^${REMOTE_NAME}$"; then
    echo -e "Gitee remote 已存在，更新 URL..."
    git remote set-url ${REMOTE_NAME} ${GITEE_URL}
else
    echo -e "添加 Gitee remote..."
    git remote add ${REMOTE_NAME} ${GITEE_URL}
fi

# 显示当前 remote 配置
echo -e "${GREEN}当前 remote 配置:${NC}"
git remote -v

# 获取最新代码
echo -e "${YELLOW}获取最新代码...${NC}"
git fetch origin

# 推送到 Gitee
echo -e "${YELLOW}推送到 Gitee...${NC}"
git push ${REMOTE_NAME} ${BRANCH} --force

echo -e "${GREEN}成功推送到 Gitee!${NC}"

# =============================================================================
# 可选：自动开启 Gitee Pages
# 需要配置 Gitee Access Token
# =============================================================================

# 检查是否配置了 GITEE_TOKEN 环境变量
if [ -n "$GITEE_TOKEN" ]; then
    echo -e "${YELLOW}尝试自动开启 Gitee Pages...${NC}"
    
    # 从 URL 提取用户名和仓库名
    # 支持 https://gitee.com/username/repo.git 格式
    REPO_PATH=$(echo $GITEE_URL | sed -E 's|https?://gitee.com/||' | sed -E 's/\.git$//')
    USERNAME=$(echo $REPO_PATH | cut -d'/' -f1)
    REPO_NAME=$(echo $REPO_PATH | cut -d'/' -f2)
    
    echo "仓库: ${USERNAME}/${REPO_NAME}"
    
    # 调用 Gitee API 开启 Pages
    # 注意：Gitee API 需要 Pro 会员才能自动开启 Pages
    RESPONSE=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: token ${GITEE_TOKEN}" \
        "https://gitee.com/api/v5/repos/${USERNAME}/${REPO_NAME}/pages/builds" \
        -d '{"branch":"'${BRANCH}'","build_type":"build"}' 2>/dev/null || true)
    
    if [ -n "$RESPONSE" ]; then
        echo -e "${GREEN}Gitee Pages 构建请求已发送${NC}"
        echo "响应: $RESPONSE"
    else
        echo -e "${YELLOW}Gitee Pages 自动构建请求发送失败，请手动开启${NC}"
    fi
else
    echo -e "${YELLOW}提示: 设置 GITEE_TOKEN 环境变量可自动开启 Gitee Pages${NC}"
    echo "获取 Token: https://gitee.com/profile/personal_access_tokens"
fi

echo -e "${GREEN}部署完成!${NC}"
echo ""
echo "Gitee 仓库地址: ${GITEE_URL}"
echo "如需开启 Pages，请访问: https://gitee.com/${USERNAME:-yourname}/${REPO_NAME:-weibo-monitor}/pages"
