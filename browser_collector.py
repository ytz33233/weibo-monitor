#!/usr/bin/env python3
"""
基于浏览器自动化的微博采集脚本
使用 requests 直接调用微博移动端 API
"""

import json
import os
import sys
import time
import random
import logging
import re
from datetime import datetime, timedelta
from urllib.parse import quote

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置
KEYWORDS = ["升金有礼", "i豆", "新动有礼", "工行升金有礼", "工行i豆", "工行新动有礼"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPO_DIR = BASE_DIR


def search_weibo(keyword: str, page: int = 1) -> list:
    """通过微博移动端 API 搜索"""
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://m.weibo.cn/search?containerid=100103type%3D1%26q%3D{quote(keyword)}",
        "X-Requested-With": "XMLHttpRequest",
    }

    containerid = f"100103type=1&q={quote(keyword)}"
    url = f"https://m.weibo.cn/api/container/getIndex"
    params = {
        "containerid": containerid,
        "page_type": "searchall",
        "page": page,
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()

        if data.get("ok") != 1:
            logger.warning(f"微博搜索 [{keyword}] 第{page}页返回非 ok: {data.get('msg', '')}")
            return results

        cards = data.get("data", {}).get("cards", [])
        for card in cards:
            if card.get("card_type") != 9:
                continue
            mblog = card.get("mblog", {})
            if not mblog:
                continue

            text = mblog.get("text", "")
            # 清理 HTML 标签
            text = re.sub(r'<[^>]+>', '', text)

            # 提取用户信息
            user = mblog.get("user", {})
            author = user.get("screen_name", "")

            # 提取互动数据
            attitudes = mblog.get("attitudes_count", 0) or 0
            comments = mblog.get("comments_count", 0) or 0
            reposts = mblog.get("reposts_count", 0) or 0

            # 提取时间
            created_at = mblog.get("created_at", "")
            mid = mblog.get("id", "")
            source_url = f"https://m.weibo.cn/detail/{mid}" if mid else ""

            # 计算热度
            heat_score = attitudes + comments * 2 + reposts * 3

            results.append({
                "id": f"weibo_{mid}",
                "sourceType": "微博",
                "author": author,
                "content": text[:500],
                "date": datetime.now().strftime("%Y-%m-%d"),
                "likes": attitudes,
                "comments": comments,
                "reposts": reposts,
                "favorites": 0,
                "heatScore": heat_score,
                "sentiment": "neutral",
                "category": "i豆兑换",
                "keywords": [keyword],
                "url": source_url,
                "collectedAt": datetime.now().isoformat(),
            })

        logger.info(f"微博搜索 [{keyword}] 第{page}页: 获取 {len(results)} 条")
        return results

    except requests.exceptions.Timeout:
        logger.error(f"微博搜索 [{keyword}] 超时")
    except Exception as e:
        logger.error(f"微博搜索 [{keyword}] 失败: {e}")

    return results


def search_xiaohongshu(keyword: str) -> list:
    """通过小红书网页搜索"""
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&source=web_search_result_notes"

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        # 小红书需要登录，如果返回登录页面则跳过
        if "登录" in resp.text[:500] or resp.status_code != 200:
            logger.warning(f"小红书搜索 [{keyword}] 需要登录，跳过")
            return results

        # 尝试从页面提取笔记数据
        # 小红书数据通常在 window.__INITIAL_STATE__ 中
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?})</script>', resp.text, re.DOTALL)
        if match:
            try:
                state = json.loads(match.group(1))
                notes = state.get("notes", [])
                for note in notes[:20]:
                    note_data = note.get("note", {})
                    if not note_data:
                        continue
                    results.append({
                        "id": f"xhs_{note_data.get('noteId', '')}",
                        "sourceType": "小红书",
                        "author": note_data.get("user", {}).get("nickname", ""),
                        "content": note_data.get("title", "") + " " + note_data.get("desc", ""),
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "likes": note_data.get("interactInfo", {}).get("likedCount", "0"),
                        "comments": note_data.get("interactInfo", {}).get("commentCount", "0"),
                        "reposts": note_data.get("interactInfo", {}).get("shareCount", "0"),
                        "favorites": note_data.get("interactInfo", {}).get("collectedCount", "0"),
                        "heatScore": 0,
                        "sentiment": "neutral",
                        "category": "i豆兑换",
                        "keywords": [keyword],
                        "url": f"https://www.xiaohongshu.com/explore/{note_data.get('noteId', '')}",
                        "collectedAt": datetime.now().isoformat(),
                    })
            except json.JSONDecodeError:
                pass

        logger.info(f"小红书搜索 [{keyword}]: 获取 {len(results)} 条")
        return results

    except Exception as e:
        logger.error(f"小红书搜索 [{keyword}] 失败: {e}")

    return results


def deduplicate(records: list) -> list:
    """去重"""
    seen = set()
    unique = []
    for r in records:
        rid = r.get("id", "")
        if rid and rid not in seen:
            seen.add(rid)
            unique.append(r)
    return unique


def save_and_push(records: list):
    """保存数据并推送到 GitHub"""
    if not records:
        logger.info("没有新数据，跳过保存")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(DATA_DIR, f"{date_str}.json")

    # 读取已有数据
    existing = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, dict):
                    existing = existing.get("records", [])
        except:
            pass

    # 合并去重
    all_ids = {r.get("id") for r in existing}
    new_records = [r for r in records if r.get("id") not in all_ids]
    merged = existing + new_records

    # 按热度排序
    merged.sort(key=lambda x: x.get("heatScore", 0), reverse=True)

    # 计算统计
    summary = {
        "total": len(merged),
        "negativeCount": sum(1 for r in merged if r.get("sentiment") == "negative"),
        "positiveCount": sum(1 for r in merged if r.get("sentiment") == "positive"),
        "neutralCount": sum(1 for r in merged if r.get("sentiment") == "neutral"),
    }

    by_source = {}
    for r in merged:
        src = r.get("sourceType", "unknown")
        by_source[src] = by_source.get(src, 0) + 1

    # 生成简报
    neg_count = summary["negativeCount"]
    brief_text = f"今日（{date_str}）共采集 {summary['total']} 条舆情"
    if neg_count > 0:
        brief_text += f"，其中需关注 {neg_count} 条负面信息"
    else:
        brief_text += "，整体态势平稳，无重大负面舆情"

    export = {
        "reportDate": date_str,
        "generatedAt": datetime.now().isoformat(),
        "dailyBrief": {
            "text": brief_text,
            "date": date_str,
            "generatedAt": datetime.now().isoformat(),
        },
        "summary": summary,
        "bySource": by_source,
        "records": merged,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"数据已保存: {output_path} (共 {len(merged)} 条, 新增 {len(new_records)} 条)")

    # Git 推送
    import subprocess
    os.chdir(REPO_DIR)
    subprocess.run(["git", "add", "data/*.json"], capture_output=True)

    result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
    if result.returncode == 0:
        logger.info("没有变更需要提交")
        return

    time_str = datetime.now().strftime("%H:%M")
    subprocess.run(["git", "commit", "-m", f"chore: 采集数据更新 {date_str} {time_str}"], capture_output=True)
    result = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)

    if result.returncode == 0:
        logger.info("推送成功！GitHub Pages 将自动更新")
    else:
        logger.error(f"推送失败: {result.stderr}")


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始数据采集...")
    logger.info("=" * 50)

    all_records = []

    # 搜索微博
    for keyword in KEYWORDS:
        logger.info(f"搜索微博: {keyword}")
        records = search_weibo(keyword, page=1)
        all_records.extend(records)
        time.sleep(random.uniform(1, 3))  # 随机延迟

    # 搜索小红书
    for keyword in KEYWORDS[:3]:  # 只搜索前3个关键词
        logger.info(f"搜索小红书: {keyword}")
        records = search_xiaohongshu(keyword)
        all_records.extend(records)
        time.sleep(random.uniform(1, 3))

    # 去重
    all_records = deduplicate(all_records)
    logger.info(f"采集完成: 共获取 {len(all_records)} 条（去重后）")

    # 保存并推送
    save_and_push(all_records)

    logger.info("=" * 50)
    logger.info("全部完成！")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
