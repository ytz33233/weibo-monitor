#!/usr/bin/env python3
"""
小红书舆情数据采集脚本 - 基于 Playwright 浏览器自动化
通过 Playwright 访问小红书搜索页面，从 __INITIAL_STATE__ 提取数据

使用方法：
1. 首次需要登录：运行脚本后会打开浏览器，手动扫码登录
2. 登录后 Cookie 会自动保存到 xhs_cookies.json
3. 后续运行自动加载 Cookie，无需重新登录
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from html import unescape

BJT = timezone(timedelta(hours=8))
KEYWORDS = ['工行i豆', '升金有礼', '新动有礼']
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xhs_cookies.json')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_xhs_date(raw_date):
    """解析小红书日期"""
    if not raw_date:
        return '未知', ''
    rel_match = re.match(r'(\d+)\s*(天|小时|分钟)前', raw_date)
    if rel_match:
        num = int(rel_match.group(1))
        unit = rel_match.group(2)
        now = datetime.now(BJT)
        if unit == '天': dt = now - timedelta(days=num)
        elif unit == '小时': dt = now - timedelta(hours=num)
        elif unit == '分钟': dt = now - timedelta(minutes=num)
        else: dt = now
        return dt.strftime('%Y-%m-%d'), dt.strftime('%Y-%m-%d %H:%M')
    short_match = re.match(r'(\d{1,2})-(\d{1,2})$', raw_date.strip())
    if short_match:
        m, d = int(short_match.group(1)), int(short_match.group(2))
        y = datetime.now(BJT).year
        return f'{y}-{m:02d}-{d:02d}', f'{y}-{m:02d}-{d:02d}'
    full_match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', raw_date)
    if full_match:
        return raw_date, raw_date
    yesterday_match = re.match(r'昨天\s*(\d{1,2}:\d{1,2})?', raw_date)
    if yesterday_match:
        dt = datetime.now(BJT) - timedelta(days=1)
        t = yesterday_match.group(1) or ''
        return dt.strftime('%Y-%m-%d'), f"{dt.strftime('%Y-%m-%d')} {t}"
    return raw_date, raw_date


def generate_title(content, keyword):
    if not content:
        return f'关于{keyword}的小红书笔记'
    title = re.sub(r'\s+', ' ', content).strip()
    if len(title) > 30:
        title = title[:30] + '...'
    return title


def simple_sentiment(text):
    negative_words = ['差', '烂', '坑', '骗', '投诉', '垃圾', '难用', '慢', '失败', '错误', '不满', '恶心', '退钱', '维权', '缩水', '一毛不拔']
    positive_words = ['好', '赞', '棒', '方便', '快', '不错', '推荐', '喜欢', '给力', '优惠', '羊毛', '白嫖', '福利', '中了', '喜提']
    neg = sum(1 for w in negative_words if w in text)
    pos = sum(1 for w in positive_words if w in text)
    if neg > pos: return 'negative'
    elif pos > neg: return 'positive'
    return 'neutral'


def categorize(text):
    if any(w in text for w in ['投诉', '问题', '失败', '错误', '不满', '维权', '缩水', '一毛不拔']):
        return '投诉反馈'
    elif any(w in text for w in ['攻略', '教程', '方法', '步骤', '怎么', '如何']):
        return '攻略分享'
    elif any(w in text for w in ['互助', '搭子', '助力']):
        return '互助交流'
    elif any(w in text for w in ['活动', '优惠', '羊毛', '福利', '领取', '签到', '抽奖', '中了']):
        return '活动推广'
    return '一般讨论'


def extract_keywords(text, keyword):
    words = set()
    words.add(keyword)
    extra = ['工行', '工商银行', 'i豆', '工银i豆', '升金', '新动', '有礼', '积分', '活动', '签到', '领取', '兑换', '立减金']
    for w in extra:
        if w in text:
            words.add(w)
    return list(words)


def extract_notes_from_js(page):
    """通过页面 JS 提取 __INITIAL_STATE__ 中的搜索结果"""
    return page.evaluate('''() => {
        try {
            for (const s of document.querySelectorAll('script')) {
                const text = s.textContent || '';
                if (!text.includes('__INITIAL_STATE__')) continue;
                
                const start = text.indexOf('__INITIAL_STATE__=');
                if (start < 0) continue;
                
                const jsonStart = start + '__INITIAL_STATE__='.length;
                let depth = 0, end = jsonStart;
                for (let i = jsonStart; i < text.length; i++) {
                    if (text[i] === '{') depth++;
                    else if (text[i] === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
                }
                
                const state = JSON.parse(text.substring(jsonStart, end));
                const notes = [];
                
                // 搜索结果在 state.search.notes 中
                const searchNotes = state.search && state.search.notes ? state.search.notes : [];
                
                for (const item of searchNotes) {
                    const note = item.note_card || item;
                    const user = note.user || {};
                    const interact = note.interact_info || {};
                    
                    notes.push({
                        id: note.id || note.note_id || '',
                        title: note.display_title || '',
                        desc: (note.desc || '').substring(0, 500),
                        author: user.nickname || '',
                        author_id: user.user_id || '',
                        time: note.time || note.last_update_time || note.ctime || '',
                        type: note.type || 'normal',
                        liked_count: interact.liked_count || '0',
                        collected_count: interact.collected_count || '0',
                        comment_count: interact.comment_count || '0',
                        share_count: interact.share_count || '0',
                        tag_list: (note.tag_list || []).map(t => t.name || t),
                        xhsh_token: note.xhsh_token || '',
                        note_url: 'https://www.xiaohongshu.com/explore/' + (note.id || note.note_id || ''),
                    });
                }
                
                return {success: true, count: notes.length, notes: notes};
            }
        } catch(e) {
            return {success: false, error: e.message};
        }
        return {success: false, error: 'No __INITIAL_STATE__ found'};
    }''')


def search_xhs(page, keyword, max_scroll=3):
    """搜索小红书笔记"""
    all_notes = []
    
    url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes&type=51"
    page.goto(url, wait_until='domcontentloaded', timeout=20000)
    time.sleep(5)
    
    # 提取数据
    result = extract_notes_from_js(page)
    
    if result.get('success'):
        notes = result['notes']
        print(f"  [OK] 第1页: 获取 {len(notes)} 条笔记")
        all_notes.extend(notes)
    else:
        print(f"  [WARN] JS 提取失败: {result.get('error', '未知')}")
        # 检查是否需要登录
        if 'login' in page.url.lower():
            print("  [ERROR] 需要登录！请先在小红书网页版扫码登录")
            return all_notes
        return all_notes
    
    # 滚动加载更多
    for i in range(max_scroll):
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(3)
        
        result = extract_notes_from_js(page)
        if result.get('success'):
            new_notes = result['notes']
            existing_ids = {n['id'] for n in all_notes}
            new_items = [n for n in new_notes if n['id'] not in existing_ids]
            if new_items:
                print(f"  [OK] 滚动第{i+1}次: 新增 {len(new_items)} 条")
                all_notes.extend(new_items)
            else:
                print(f"  [INFO] 滚动第{i+1}次: 无新数据")
                break
        else:
            break
    
    return all_notes


def save_cookies(context, path):
    """保存 Cookie 到文件"""
    cookies = context.cookies()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, indent=2)
    print(f"  Cookie 已保存: {path} ({len(cookies)} 个)")


def load_cookies(context, path):
    """从文件加载 Cookie"""
    if not os.path.exists(path):
        return False
    with open(path, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    context.add_cookies(cookies)
    print(f"  Cookie 已加载: {path} ({len(cookies)} 个)")
    return True


def build_xhs_records(notes, keyword):
    """将小红书笔记转换为统一记录格式"""
    records = []
    for i, note in enumerate(notes):
        date_str, publish_time = parse_xhs_date(note.get('time', ''))
        content = clean_html(note.get('desc', ''))
        title = note.get('title', '') or generate_title(content, keyword)
        author = note.get('author', '未知')
        
        try:
            likes = int(note.get('liked_count', '0') or '0')
        except:
            likes = 0
        try:
            comments = int(note.get('comment_count', '0') or '0')
        except:
            comments = 0
        try:
            favorites = int(note.get('collected_count', '0') or '0')
        except:
            favorites = 0
        try:
            shares = int(note.get('share_count', '0') or '0')
        except:
            shares = 0
        
        heat = likes * 1 + comments * 2 + favorites * 2 + shares * 1
        
        records.append({
            'id': f"XHS_{i+1:04d}",
            'sourceType': 'xiaohongshu',
            'source': author,
            'author': author,
            'title': title,
            'content': content,
            'date': date_str,
            'publishTime': publish_time,
            'likes': likes,
            'comments': comments,
            'reposts': shares,
            'favorites': favorites,
            'heatScore': heat,
            'sentiment': simple_sentiment(title + ' ' + content),
            'category': categorize(title + ' ' + content),
            'keywords': extract_keywords(title + ' ' + content, keyword),
            'url': note.get('note_url', ''),
            'collectedAt': datetime.now(BJT).isoformat(),
            'searchKeyword': keyword,
            'status': '待处理',
            'xhsNoteId': note.get('id', ''),
            'tags': note.get('tag_list', []),
        })
    
    return records


def main():
    from playwright.sync_api import sync_playwright

    print("=" * 60)
    print(f"小红书舆情数据采集 - {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        # 尝试加载已保存的 Cookie
        print("\n[1/4] 加载登录状态...")
        has_cookies = load_cookies(context, COOKIE_FILE)

        # 访问小红书首页
        print("\n[2/4] 访问小红书首页...")
        page.goto('https://www.xiaohongshu.com/explore', wait_until='domcontentloaded', timeout=20000)
        time.sleep(3)

        # 检查是否已登录
        if not has_cookies:
            # 首次运行，保存当前 Cookie（即使未登录也保存）
            save_cookies(context, COOKIE_FILE)
            print("  [INFO] 首次运行，Cookie 已保存")
            print("  [WARN] 未登录状态下搜索功能受限")
            print("  [提示] 如需采集小红书数据，请通过 SOLO 浏览器手动登录后重新获取 Cookie")
        else:
            # 检查登录状态
            is_logged_in = page.evaluate('''() => {
                const loginBtn = document.querySelector('[class*="login"]');
                const profileLink = document.querySelector('a[href*="/user/profile"]');
                return profileLink !== null || loginBtn === null;
            }''')
            print(f"  登录状态: {'✅ 已登录' if is_logged_in else '❌ 未登录'}")
            
            if is_logged_in:
                # 更新 Cookie
                save_cookies(context, COOKIE_FILE)

        # 搜索采集
        print("\n[3/4] 开始搜索采集...")
        for keyword in KEYWORDS:
            print(f"\n--- 搜索: {keyword} ---")
            notes = search_xhs(page, keyword, max_scroll=2)
            
            if notes:
                records = build_xhs_records(notes, keyword)
                all_records.extend(records)
                print(f"  转换为 {len(records)} 条记录")
            else:
                print(f"  未获取到数据")

        browser.close()

    # 去重
    seen = set()
    unique = []
    for r in all_records:
        if r['url'] not in seen:
            seen.add(r['url'])
            unique.append(r)

    print(f"\n[4/4] 数据汇总...")
    print(f"  总采集: {len(all_records)} 条")
    print(f"  去重后: {len(unique)} 条")

    # 保存
    date_str = datetime.now(BJT).strftime('%Y-%m-%d')
    output_path = os.path.join(OUTPUT_DIR, f"{date_str}.json")
    
    # 如果文件已存在（微博数据），合并
    existing_data = None
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    
    if existing_data and 'records' in existing_data:
        # 合并数据
        existing_ids = {r.get('url', '') for r in existing_data['records']}
        new_records = [r for r in unique if r['url'] not in existing_ids]
        existing_data['records'].extend(new_records)
        
        # 更新统计
        total = len(existing_data['records'])
        neg = sum(1 for r in existing_data['records'] if r['sentiment'] == 'negative')
        pos = sum(1 for r in existing_data['records'] if r['sentiment'] == 'positive')
        neu = total - neg - pos
        
        existing_data['summary']['total'] = total
        existing_data['summary']['negativeCount'] = neg
        existing_data['summary']['positiveCount'] = pos
        existing_data['summary']['neutralCount'] = neu
        
        # 更新 bySource
        xhs_count = sum(1 for r in existing_data['records'] if r['sourceType'] == 'xiaohongshu')
        existing_data['bySource']['xiaohongshu'] = xhs_count
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        print(f"  已合并到现有文件: {output_path}")
        print(f"  新增小红书数据: {len(new_records)} 条")
    else:
        # 新建文件
        daily_data = {
            "reportDate": date_str,
            "generatedAt": datetime.now(BJT).isoformat(),
            "dailyBrief": {
                "text": f"今日（{date_str}）共采集 {len(unique)} 条舆情（小红书）",
                "date": date_str,
                "generatedAt": datetime.now(BJT).isoformat(),
                "totalPosts": len(unique),
                "negativeCount": sum(1 for r in unique if r['sentiment'] == 'negative'),
            },
            "summary": {
                "total": len(unique),
                "negativeCount": sum(1 for r in unique if r['sentiment'] == 'negative'),
                "positiveCount": sum(1 for r in unique if r['sentiment'] == 'positive'),
                "neutralCount": sum(1 for r in unique if r['sentiment'] == 'neutral'),
            },
            "bySource": {"xiaohongshu": len(unique)},
            "records": unique
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(daily_data, f, ensure_ascii=False, indent=2)
        print(f"  数据已保存: {output_path}")

    return output_path


if __name__ == '__main__':
    output = main()
    if output:
        print(f"\n输出文件: {output}")
