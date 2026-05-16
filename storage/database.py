import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional

from models import SentimentRecord
import config

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sentiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    keyword TEXT NOT NULL,
    record_id TEXT NOT NULL,
    title TEXT,
    content TEXT,
    author TEXT,
    author_id TEXT,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    collects INTEGER DEFAULT 0,
    created_at TEXT,
    collected_at TEXT NOT NULL,
    raw_data TEXT,
    UNIQUE(platform, record_id)
);
CREATE INDEX IF NOT EXISTS idx_platform ON sentiments(platform);
CREATE INDEX IF NOT EXISTS idx_keyword ON sentiments(keyword);
CREATE INDEX IF NOT EXISTS idx_collected_at ON sentiments(collected_at);
"""


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript(CREATE_TABLE_SQL)
        self.conn.commit()

    def insert_records(self, records: list[SentimentRecord]) -> int:
        inserted = 0
        for r in records:
            try:
                cursor = self.conn.execute(
                    """INSERT OR IGNORE INTO sentiments
                    (platform, keyword, record_id, title, content, author, author_id,
                     likes, comments, shares, collects, created_at, collected_at, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        r.platform, r.keyword, r.record_id, r.title, r.content,
                        r.author, r.author_id, r.likes, r.comments, r.shares,
                        r.collects,
                        r.created_at.isoformat() if r.created_at else None,
                        r.collected_at.isoformat() if r.collected_at else None,
                        json.dumps(r.raw_data, ensure_ascii=False),
                    ),
                )
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                logger.error(f"插入记录失败 {r.platform}/{r.record_id}: {e}")
        self.conn.commit()
        return inserted

    def query(
        self,
        platform: Optional[str] = None,
        keyword: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        conditions = []
        params = []
        if platform:
            conditions.append("platform = ?")
            params.append(platform)
        if keyword:
            conditions.append("keyword = ?")
            params.append(keyword)
        if start_date:
            conditions.append("collected_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("collected_at <= ?")
            params.append(end_date)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM sentiments{where} ORDER BY collected_at DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_summary(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM sentiments").fetchone()[0]
        weibo_count = self.conn.execute(
            "SELECT COUNT(*) FROM sentiments WHERE platform='weibo'"
        ).fetchone()[0]
        xhs_count = self.conn.execute(
            "SELECT COUNT(*) FROM sentiments WHERE platform='xhs'"
        ).fetchone()[0]
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = self.conn.execute(
            "SELECT COUNT(*) FROM sentiments WHERE collected_at >= ?", (today,)
        ).fetchone()[0]
        total_interactions = self.conn.execute(
            "SELECT COALESCE(SUM(likes + comments + shares + collects), 0) FROM sentiments"
        ).fetchone()[0]
        last_collected = self.conn.execute(
            "SELECT MAX(collected_at) FROM sentiments"
        ).fetchone()[0]
        return {
            "total": total,
            "weibo_count": weibo_count,
            "xhs_count": xhs_count,
            "today_count": today_count,
            "total_interactions": total_interactions,
            "last_collected": last_collected,
        }

    def get_keyword_stats(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT keyword, platform, COUNT(*) as count,
               SUM(likes) as total_likes, SUM(comments) as total_comments,
               SUM(shares) as total_shares, SUM(collects) as total_collects
               FROM sentiments GROUP BY keyword, platform"""
        ).fetchall()
        return [dict(row) for row in rows]

    def get_daily_trend(self, days: int = 30) -> list[dict]:
        rows = self.conn.execute(
            """SELECT DATE(collected_at) as date, platform, COUNT(*) as count,
               SUM(likes + comments + shares + collects) as interactions
               FROM sentiments
               WHERE collected_at >= DATE('now', ?)
               GROUP BY DATE(collected_at), platform
               ORDER BY date""",
            (f"-{days} days",),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self):
        self.conn.close()
