#!/usr/bin/env python3
"""
独立的数据采集脚本，用于 GitHub Actions 运行
"""

import os
import sys
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    """执行数据采集"""
    try:
        from scheduler import run_collection
        
        logger.info("=" * 50)
        logger.info(f"Starting collection at {datetime.now().isoformat()}")
        logger.info("=" * 50)
        
        run_collection()
        
        logger.info("=" * 50)
        logger.info(f"Collection completed at {datetime.now().isoformat()}")
        logger.info("=" * 50)
        
        return 0
        
    except Exception as e:
        logger.error(f"Collection failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
