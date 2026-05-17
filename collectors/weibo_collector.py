import asyncio
import json
import logging
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from models import SentimentRecord
from utils import clean_html, extract_title, parse_number, parse_weibo_time
import config

logger = logging.getLogger(__name__)


class WeiboCollector:
    def __init__(self):
        self.server_params = StdioServerParameters(
            command=config.WEIBO_MCP_COMMAND,
            args=config.WEIBO_MCP_ARGS,
        )

    async def _call_tool(self, tool_name: str, arguments: dict) -> list:
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                data = []
                for item in result.content:
                    if hasattr(item, "text") and item.text:
                        parsed = json.loads(item.text)
                        if isinstance(parsed, list):
                            data.extend(parsed)
                        else:
                            data.append(parsed)
                return data

    async def search(self, keyword: str, limit: int = 20, page: int = 1) -> list[SentimentRecord]:
        try:
            raw_list = await self._call_tool(
                "search_content",
                {"keyword": keyword, "limit": limit, "page": page},
            )
            records = []
            for item in raw_list:
                text_raw = item.get("text", "")
                text_clean = clean_html(text_raw)
                user = item.get("user", {})
                created_at = parse_weibo_time(item.get("created_at", ""))
                record = SentimentRecord(
                    platform="weibo",
                    keyword=keyword,
                    record_id=str(item.get("id", "")),
                    title=extract_title(text_clean),
                    content=text_clean,
                    author=user.get("screen_name", ""),
                    author_id=str(user.get("id", "")),
                    likes=parse_number(item.get("attitudes_count", 0)),
                    comments=parse_number(item.get("comments_count", 0)),
                    shares=parse_number(item.get("reposts_count", 0)),
                    collects=0,
                    created_at=created_at,
                    raw_data=item,
                )
                records.append(record)
            logger.info(f"微博搜索 '{keyword}' 获取 {len(records)} 条结果")
            return records
        except Exception as e:
            logger.error(f"微博搜索 '{keyword}' 失败: {e}")
            return []

    def search_sync(self, keyword: str, limit: int = 20) -> list[SentimentRecord]:
        return asyncio.run(self.search(keyword, limit))

    async def check_connection(self) -> bool:
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return True
        except Exception:
            return False
