#!/usr/bin/env python3
"""
本地采集 + 推送 GitHub 脚本
在本地运行采集，然后将数据文件推送到 GitHub 仓库
"""

import os
import sys
import subprocess
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 仓库配置
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
GITHUB_REPO = "ytz33233/weibo-monitor"


def run_collection():
    """运行数据采集"""
    logger.info("=" * 50)
    logger.info("开始数据采集...")
    logger.info("=" * 50)

    from scheduler import run_collection
    run_collection()

    logger.info("数据采集完成")


def git_push():
    """将数据文件推送到 GitHub"""
    logger.info("=" * 50)
    logger.info("推送数据到 GitHub...")
    logger.info("=" * 50)

    os.chdir(REPO_DIR)

    # 添加数据文件
    subprocess.run(["git", "add", "data/*.json"], capture_output=True)
    subprocess.run(["git", "add", "data/sentiment_monitor.db"], capture_output=True)

    # 检查是否有变更
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True
    )

    if result.returncode == 0:
        logger.info("没有新的数据变更，跳过推送")
        return

    # 提交
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")
    commit_msg = f"chore: 采集数据更新 {date_str} {time_str}"

    subprocess.run(
        ["git", "commit", "-m", commit_msg],
        capture_output=True
    )
    logger.info(f"提交: {commit_msg}")

    # 推送
    result = subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        logger.info("推送成功！")
    else:
        logger.error(f"推送失败: {result.stderr}")


def main():
    """主函数"""
    try:
        run_collection()
        git_push()
        logger.info("=" * 50)
        logger.info("全部完成！")
        logger.info("=" * 50)
        return 0
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
