import json
import logging
from typing import Optional

import httpx

from models import SentimentRecord
from utils import clean_html, parse_number, timestamp_to_datetime
import config

logger = logging.getLogger(__name__)


class XhsCollector:
    def __init__(self):
        self.url = config.XHS_MCP_URL
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _call_tool(self, tool_name: str, arguments: dict) -> any:
        async with httpx.AsyncClient(timeout=60) as client:
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }
            resp = await client.post(
                self.url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            resp.raise_for_status()
            text = resp.text
            for line in text.split("\n"):
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str:
                        data = json.loads(data_str)
                        result = data.get("result", {})
                        content_list = result.get("content", [])
                        for item in content_list:
                            if item.get("type") == "text" and item.get("text"):
                                return json.loads(item["text"])
            return None

    async def search(self, keyword: str, limit: int = 20) -> list[SentimentRecord]:
        try:
            feeds_data = await self._call_tool(
                "search_feeds",
                {"keyword": keyword, "sort": "general", "note_type": 0},
            )
            if not feeds_data:
                return []

            feeds = feeds_data.get("feeds", [])
            records = []
            count = 0
            for feed in feeds:
                if count >= limit:
                    break
                note_id = feed.get("id", "")
                xsec_token = feed.get("xsec_token", "")

                title = feed.get("title", "")
                author = feed.get("user", "")
                author_id = feed.get("user_id", "")
                likes = parse_number(feed.get("likes", 0))

                detail = None
                if note_id and xsec_token:
                    try:
                        detail = await self._call_tool(
                            "get_feed_detail",
                            {"note_id": note_id, "xsec_token": xsec_token},
                        )
                    except Exception as e:
                        logger.warning(f"获取小红书笔记详情失败 {note_id}: {e}")

                if detail:
                    desc = clean_html(detail.get("desc", ""))
                    comments = parse_number(detail.get("comments", 0))
                    collects = parse_number(detail.get("collects", 0))
                    shares = parse_number(detail.get("share_count", 0))
                    time_ts = detail.get("time")
                    created_at = timestamp_to_datetime(time_ts) if time_ts else None
                    if not title:
                        title = detail.get("title", "")
                else:
                    desc = ""
                    comments = 0
                    collects = 0
                    shares = 0
                    created_at = None

                record = SentimentRecord(
                    platform="xhs",
                    keyword=keyword,
                    record_id=str(note_id),
                    title=clean_html(title),
                    content=desc,
                    author=author,
                    author_id=str(author_id),
                    likes=likes,
                    comments=comments,
                    shares=shares,
                    collects=collects,
                    created_at=created_at,
                    raw_data={"feed": feed, "detail": detail} if detail else {"feed": feed},
                )
                records.append(record)
                count += 1

            logger.info(f"小红书搜索 '{keyword}' 获取 {len(records)} 条结果")
            return records
        except Exception as e:
            logger.error(f"小红书搜索 '{keyword}' 失败: {e}")
            return []

    def search_sync(self, keyword: str, limit: int = 20) -> list[SentimentRecord]:
        import asyncio
        return asyncio.run(self.search(keyword, limit))

    async def check_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "monitor", "version": "1.0"},
                    },
                }
                resp = await client.post(
                    self.url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    },
                )
                return resp.status_code == 200
        except Exception:
            return False
