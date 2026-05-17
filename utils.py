import re
from datetime import datetime
from bs4 import BeautifulSoup


def clean_html(text: str) -> str:
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def parse_number(val) -> int:
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    s = str(val).strip()
    if not s or s == "-":
        return 0
    m = re.match(r"([\d.]+)\s*万", s)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.match(r"([\d.]+)\s*亿", s)
    if m:
        return int(float(m.group(1)) * 100000000)
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def extract_title(text: str, max_len: int = 30) -> str:
    cleaned = clean_html(text)
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len] + "..."


def timestamp_to_datetime(ts) -> datetime:
    if ts is None:
        return None
    try:
        ts_int = int(ts)
        if ts_int < 1e12:
            ts_int *= 1000
        return datetime.fromtimestamp(ts_int / 1000)
    except (ValueError, TypeError, OSError):
        return None


def parse_weibo_time(time_str: str) -> datetime:
    if not time_str:
        return None
    now = datetime.now()
    if "分钟前" in time_str:
        mins = int(re.search(r"(\d+)", time_str).group(1))
        return now - __import__("datetime").timedelta(minutes=mins)
    if "小时前" in time_str:
        hours = int(re.search(r"(\d+)", time_str).group(1))
        return now - __import__("datetime").timedelta(hours=hours)
    if "昨天" in time_str:
        return now - __import__("datetime").timedelta(days=1)
    if "前天" in time_str:
        return now - __import__("datetime").timedelta(days=2)
    for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M", "%m月%d日 %H:%M", "%Y年%m月%d日 %H:%M"]:
        try:
            return datetime.strptime(time_str.strip(), fmt)
        except ValueError:
            continue
    return None


def deduplicate(records: list) -> list:
    seen = set()
    result = []
    for r in records:
        key = (r.platform, r.record_id)
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result
