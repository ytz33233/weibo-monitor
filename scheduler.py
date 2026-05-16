import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from collectors.weibo_collector import WeiboCollector
from collectors.xhs_collector import XhsCollector
from storage.database import Database
from storage.exporter import export_excel, export_json
from utils import deduplicate
import config

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
_db: Database = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def run_collection():
    logger.info(f"=== 开始定时采集 {datetime.now().isoformat()} ===")
    db = _get_db()
    weibo = WeiboCollector()
    xhs = XhsCollector()
    all_records = []

    for keyword in config.KEYWORDS:
        try:
            weibo_records = weibo.search_sync(keyword, config.SEARCH_LIMIT)
            all_records.extend(weibo_records)
        except Exception as e:
            logger.error(f"微博采集失败 [{keyword}]: {e}")

        try:
            xhs_records = xhs.search_sync(keyword, config.SEARCH_LIMIT)
            all_records.extend(xhs_records)
        except Exception as e:
            logger.error(f"小红书采集失败 [{keyword}]: {e}")

    all_records = deduplicate(all_records)
    inserted = db.insert_records(all_records)
    logger.info(f"=== 采集完成: 获取 {len(all_records)} 条, 新增 {inserted} 条 ===")

    try:
        export_excel(db)
        export_json(db)
        logger.info("自动导出完成")
    except Exception as e:
        logger.error(f"自动导出失败: {e}")


def start_scheduler():
    for hour in config.SCHEDULE_HOURS:
        scheduler.add_job(
            run_collection,
            CronTrigger(hour=hour, minute=0),
            id=f"daily_{hour}",
            name=f"每日{hour}:00采集",
            replace_existing=True,
        )
    scheduler.start()
    logger.info(f"定时任务已启动: 每日 {config.SCHEDULE_HOURS} 点自动采集")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("定时任务已停止")


def get_jobs_info():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else "无",
            "trigger": str(job.trigger),
        })
    return jobs


def trigger_now():
    scheduler.modify_job("daily_9", next_run_time=datetime.now())
    logger.info("已触发立即采集")
