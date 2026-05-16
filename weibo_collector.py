#!/usr/bin/env python3
"""
微博舆情数据采集脚本 - 使用 Playwright 浏览器自动化
通过浏览器访问微博移动端 API 获取搜索结果数据
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from html import unescape

# 关键词列表
KEYWORDS = ['工行i豆', '升金有礼', '新动有礼']

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 北京时区
BJT = timezone(timedelta(hours=8))


def clean_html(text):
    """清理 HTML 标签，提取纯文本"""
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_mblogs_from_json(api_data):
    """从 API JSON 数据中提取微博列表"""
    mblogs = []
    cards = api_data.get('data', {}).get('cards', [])
    for card in cards:
        if card.get('card_type') == 9 and 'mblog' in card:
            mb = card['mblog']
            user = mb.get('user', {})
            mblogs.append({
                'id': mb.get('id', ''),
                'mid': mb.get('mid', ''),
                'author': user.get('screen_name', ''),
                'author_id': user.get('id', ''),
                'verified': user.get('verified', False),
                'verified_reason': user.get('verified_reason', ''),
                'followers': user.get('followers_count', 0),
                'content': clean_html(mb.get('text', '')),
                'content_raw': mb.get('text_raw', ''),
                'created_at': mb.get('created_at', ''),
                'source': mb.get('source', ''),
                'reposts': mb.get('reposts_count', 0),
                'comments': mb.get('comments_count', 0),
                'likes': mb.get('attitudes_count', 0),
                'favorites': mb.get('favorites_count', 0) or 0,
                'is_long_text': mb.get('isLongText', False),
                'pics': len(mb.get('pics', [])),
                'page_info': mb.get('page_info', {}),
                'url': f"https://m.weibo.cn/detail/{mb.get('mid', mb.get('id', ''))}",
            })
    return mblogs


def search_weibo(page, keyword, max_pages=3):
    """搜索微博，返回微博列表"""
    all_mblogs = []
    for page_num in range(1, max_pages + 1):
        containerid = f"100103type%3D1%26q%3D{keyword}"
        url = f"https://m.weibo.cn/api/container/getIndex?containerid={containerid}&page_type=searchall&page={page_num}"

        try:
            resp = page.goto(url, wait_until='domcontentloaded', timeout=15000)
            if not resp:
                print(f"  [WARN] 页面加载失败: {keyword} page={page_num}")
                break

            # 获取页面文本内容（JSON）
            content = page.inner_text('body') or page.evaluate('() => document.body.innerText')
            if not content:
                print(f"  [WARN] 页面内容为空: {keyword} page={page_num}")
                break

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                print(f"  [WARN] JSON 解析失败: {keyword} page={page_num}, 内容前100字: {content[:100]}")
                break

            if data.get('ok') != 1:
                print(f"  [WARN] API 返回非 ok: {data.get('ok')}, msg: {data.get('msg', '')}")
                break

            mblogs = extract_mblogs_from_json(data)
            if not mblogs:
                print(f"  [INFO] 无更多数据: {keyword} page={page_num}")
                break

            all_mblogs.extend(mblogs)
            print(f"  [OK] {keyword} 第{page_num}页: 获取 {len(mblogs)} 条微博")

            # 检查是否还有更多
            cardlist_info = data.get('data', {}).get('cardlistInfo', {})
            total = cardlist_info.get('total', 0)
            if len(all_mblogs) >= total or len(all_mblogs) >= 30:
                break

            time.sleep(1)  # 礼貌性延迟

        except Exception as e:
            print(f"  [ERROR] {keyword} page={page_num}: {e}")
            break

    return all_mblogs


def compute_heat_score(mb):
    """计算热度分数"""
    return mb['reposts'] * 3 + mb['comments'] * 2 + mb['likes'] * 1


def simple_sentiment(text):
    """简单情感分析"""
    negative_words = ['差', '烂', '坑', '骗', '投诉', '垃圾', '难用', '慢', '失败', '错误', '不满', '恶心', '退钱', '维权']
    positive_words = ['好', '赞', '棒', '方便', '快', '不错', '推荐', '喜欢', '给力', '优惠', '羊毛', '白嫖', '福利']

    neg_count = sum(1 for w in negative_words if w in text)
    pos_count = sum(1 for w in positive_words if w in text)

    if neg_count > pos_count:
        return 'negative'
    elif pos_count > neg_count:
        return 'positive'
    return 'neutral'


def parse_weibo_date(raw_date):
    """将微博原始日期格式转换为 YYYY-MM-DD 和可读格式
    微博格式示例: 'Mon Dec 01 10:15:57 +0800 2025', '5-10 10:04', '16小时前'
    """
    if not raw_date:
        return '未知', '', raw_date

    # 格式1: 完整日期如 "Mon Dec 01 10:15:57 +0800 2025" 或 "Wed May 06 14:39:54 +0800 2026"
    full_patterns = [
        '%a %b %d %H:%M:%S %z %Y',  # Mon Dec 01 10:15:57 +0800 2025
    ]
    for pat in full_patterns:
        try:
            dt = datetime.strptime(raw_date, pat)
            return dt.strftime('%Y-%m-%d'), dt.strftime('%Y-%m-%d %H:%M'), raw_date
        except ValueError:
            continue

    # 格式2: 短日期如 "5-10 10:04" 或 "2025-12-1"
    short_match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', raw_date)
    if short_match:
        y, m, d = int(short_match.group(1)), int(short_match.group(2)), int(short_match.group(3))
        return f'{y}-{m:02d}-{d:02d}', f'{y}-{m:02d}-{d:02d}', raw_date

    short_match2 = re.match(r'(\d{1,2})-(\d{1,2})\s+(\d{1,2}:\d{1,2})', raw_date)
    if short_match2:
        m, d = int(short_match2.group(1)), int(short_match2.group(2))
        t = short_match2.group(3)
        now = datetime.now(BJT)
        y = now.year
        return f'{y}-{m:02d}-{d:02d}', f'{y}-{m:02d}-{d:02d} {t}', raw_date

    # 格式3: 相对时间如 "16小时前", "3分钟前"
    rel_match = re.match(r'(\d+)\s*(小时|分钟|天)前', raw_date)
    if rel_match:
        num = int(rel_match.group(1))
        unit = rel_match.group(2)
        now = datetime.now(BJT)
        if unit == '小时':
            dt = now - timedelta(hours=num)
        elif unit == '分钟':
            dt = now - timedelta(minutes=num)
        elif unit == '天':
            dt = now - timedelta(days=num)
        else:
            dt = now
        return dt.strftime('%Y-%m-%d'), dt.strftime('%Y-%m-%d %H:%M'), raw_date

    return '未知', '', raw_date


def generate_title(content, keyword, author):
    """根据内容自动生成标题"""
    if not content:
        return f'{author}关于{keyword}的微博'
    # 取内容前30个字符作为标题，去除换行和多余空格
    title = re.sub(r'\s+', ' ', content).strip()
    if len(title) > 30:
        title = title[:30] + '...'
    return title


def categorize(text):
    """分类"""
    if any(w in text for w in ['投诉', '问题', '失败', '错误', '不满', '维权']):
        return '投诉反馈'
    elif any(w in text for w in ['活动', '优惠', '羊毛', '福利', '白嫖', '领取', '签到']):
        return '活动推广'
    elif any(w in text for w in ['攻略', '教程', '方法', '步骤', '怎么']):
        return '攻略分享'
    return '一般讨论'


def extract_keywords(text, keyword):
    """提取关键词"""
    words = set()
    words.add(keyword)
    extra_words = ['工行', '工商银行', 'i豆', '升金', '新动', '有礼', '积分', '活动', '签到', '领取']
    for w in extra_words:
        if w in text:
            words.add(w)
    return list(words)


def build_daily_json(all_records):
    """构建每日 JSON 数据"""
    now = datetime.now(BJT)
    date_str = now.strftime('%Y-%m-%d')

    total = len(all_records)
    neg_count = sum(1 for r in all_records if r['sentiment'] == 'negative')
    pos_count = sum(1 for r in all_records if r['sentiment'] == 'positive')
    neu_count = total - neg_count - pos_count

    # 按来源分组
    by_source = {}
    for r in all_records:
        src = r['sourceType']
        by_source[src] = by_source.get(src, 0) + 1

    # 按关键词分组统计
    by_keyword = {}
    for r in all_records:
        for kw in r.get('keywords', []):
            by_keyword[kw] = by_keyword.get(kw, 0) + 1

    # 热度排行
    top_hot = sorted(all_records, key=lambda x: x['heatScore'], reverse=True)[:5]

    neg_records = [r for r in all_records if r['sentiment'] == 'negative']

    brief_text = f"今日（{date_str}）共采集 {total} 条舆情"
    if neg_count > 0:
        brief_text += f"，其中负面 {neg_count} 条，需关注"
    else:
        brief_text += "，整体态势平稳，无重大负面舆情"

    return {
        "reportDate": date_str,
        "generatedAt": now.isoformat(),
        "dailyBrief": {
            "text": brief_text,
            "date": date_str,
            "generatedAt": now.isoformat(),
            "totalPosts": total,
            "negativeCount": neg_count,
            "topKeywords": dict(sorted(by_keyword.items(), key=lambda x: x[1], reverse=True)[:10]),
            "hotPosts": [{"author": r['author'], "content": r['content'][:50], "heat": r['heatScore']} for r in top_hot]
        },
        "summary": {
            "total": total,
            "negativeCount": neg_count,
            "positiveCount": pos_count,
            "neutralCount": neu_count,
            "byKeyword": by_keyword
        },
        "bySource": by_source,
        "records": all_records
    }


def main():
    from playwright.sync_api import sync_playwright

    print("=" * 60)
    print(f"微博舆情数据采集 - {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_records = []
    record_id = 1

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 10; Pixel 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
            viewport={'width': 375, 'height': 812}
        )
        page = context.new_page()

        # 先访问微博首页获取 cookies
        print("\n[1/3] 访问微博首页获取 session...")
        page.goto('https://m.weibo.cn', wait_until='domcontentloaded', timeout=20000)
        time.sleep(2)

        # 搜索每个关键词
        print(f"\n[2/3] 开始搜索采集...")
        for keyword in KEYWORDS:
            print(f"\n--- 搜索关键词: {keyword} ---")
            mblogs = search_weibo(page, keyword, max_pages=2)

            for mb in mblogs:
                sentiment = simple_sentiment(mb['content'])
                date_str, publish_time, raw_date = parse_weibo_date(mb['created_at'])
                title = generate_title(mb['content'], keyword, mb['author'])
                all_records.append({
                    'id': f"WB_{record_id:04d}",
                    'sourceType': 'weibo',
                    'source': mb['author'],       # 前端用 source 显示发布者
                    'author': mb['author'],       # 保留 author 字段
                    'title': title,               # 根据内容自动生成标题
                    'content': mb['content'],
                    'date': date_str,             # 转换为 YYYY-MM-DD 格式
                    'publishTime': publish_time,  # 详细时间 YYYY-MM-DD HH:MM
                    'likes': mb['likes'],
                    'comments': mb['comments'],
                    'reposts': mb['reposts'],
                    'favorites': mb['favorites'],
                    'heatScore': compute_heat_score(mb),
                    'sentiment': sentiment,
                    'category': categorize(mb['content']),
                    'keywords': extract_keywords(mb['content'], keyword),
                    'url': mb['url'],
                    'collectedAt': datetime.now(BJT).isoformat(),
                    'searchKeyword': keyword,
                    'status': '待处理',           # 默认处理状态
                })
                record_id += 1

        browser.close()

    # 去重（按 mid）
    seen = set()
    unique_records = []
    for r in all_records:
        if r['url'] not in seen:
            seen.add(r['url'])
            unique_records.append(r)

    print(f"\n[3/3] 数据汇总...")
    print(f"  总采集: {len(all_records)} 条")
    print(f"  去重后: {len(unique_records)} 条")

    # 构建并保存 JSON
    daily_data = build_daily_json(unique_records)
    date_str = daily_data['reportDate']
    output_path = os.path.join(OUTPUT_DIR, f"{date_str}.json")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 数据已保存到: {output_path}")
    print(f"   总计: {daily_data['summary']['total']} 条")
    print(f"   正面: {daily_data['summary']['positiveCount']} 条")
    print(f"   负面: {daily_data['summary']['negativeCount']} 条")
    print(f"   中性: {daily_data['summary']['neutralCount']} 条")

    return output_path


if __name__ == '__main__':
    output = main()
    print(f"\n输出文件: {output}")
