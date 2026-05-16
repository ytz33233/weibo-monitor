import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KEYWORDS = ["升金有礼", "i豆", "新动有礼", "工行升金有礼", "工行i豆", "工行新动有礼"]

WEIBO_MCP_COMMAND = "node"
WEIBO_MCP_ARGS = ["/data/user/work/mcp-server-weibo/dist/index.js"]

XHS_MCP_URL = "http://127.0.0.1:18060/mcp"

DB_PATH = os.path.join(BASE_DIR, "data", "sentiment_monitor.db")
EXPORT_DIR = os.path.join(BASE_DIR, "data", "exports")

SEARCH_LIMIT = 20

SCHEDULE_HOURS = [9, 18]
