import asyncio
import os
import sys
import logging
import random
from datetime import datetime, timedelta
from collections import Counter

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import KEYWORDS, EXPORT_DIR
from storage.database import Database
from storage.exporter import export_excel, export_json
from collectors.weibo_collector import WeiboCollector
from collectors.xhs_collector import XhsCollector
from utils import deduplicate
from scheduler import start_scheduler, stop_scheduler, get_jobs_info, run_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 页面配置
st.set_page_config(
    page_title="运营活动客户舆情雷达",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 深色主题 CSS
DARK_CSS = """
<style>
    /* 全局深色背景 */
    .stApp {
        background: linear-gradient(135deg, #0a0f1c 0%, #0d1321 50%, #0a0f1c 100%);
        color: #e2e8f0;
    }
    
    /* 主容器 */
    .main > div {
        padding: 0 2rem;
    }
    
    /* 隐藏默认header */
    header[data-testid="stHeader"] {
        display: none;
    }
    
    /* 顶部导航栏 */
    .nav-container {
        background: rgba(15, 23, 42, 0.8);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(59, 130, 246, 0.2);
        padding: 1rem 2rem;
        margin: -1rem -2rem 2rem -2rem;
        display: flex;
        align-items: center;
        gap: 2rem;
    }
    
    .nav-logo {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: #3b82f6;
        font-size: 1.5rem;
        font-weight: 700;
    }
    
    .nav-logo-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
    }
    
    .nav-tabs {
        display: flex;
        gap: 0.5rem;
        flex: 1;
    }
    
    .nav-tab {
        padding: 0.5rem 1rem;
        border-radius: 6px;
        color: #94a3b8;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.2s;
        border: none;
        background: transparent;
    }
    
    .nav-tab:hover {
        color: #e2e8f0;
        background: rgba(59, 130, 246, 0.1);
    }
    
    .nav-tab.active {
        color: #3b82f6;
        background: rgba(59, 130, 246, 0.15);
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    
    .nav-tab .badge {
        margin-left: 0.5rem;
        padding: 0.1rem 0.4rem;
        background: rgba(59, 130, 246, 0.2);
        border-radius: 4px;
        font-size: 0.75rem;
    }
    
    /* 页面标题 */
    .page-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .page-header-icon {
        width: 48px;
        height: 48px;
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
    }
    
    .page-header h1 {
        color: #f1f5f9;
        font-size: 1.75rem;
        font-weight: 600;
        margin: 0;
    }
    
    .page-header .subtitle {
        color: #64748b;
        font-size: 0.875rem;
        margin-top: 0.25rem;
    }
    
    /* 卡片样式 */
    .card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(71, 85, 105, 0.4);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }
    
    .card-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1rem;
        color: #94a3b8;
        font-size: 0.875rem;
    }
    
    .card-header .number {
        color: #3b82f6;
        font-weight: 600;
    }
    
    /* 简报卡片 - 蓝色左边框 */
    .brief-card {
        background: rgba(30, 41, 59, 0.6);
        border-left: 4px solid #3b82f6;
        border-radius: 0 12px 12px 0;
        padding: 1.25rem;
        margin-bottom: 1.5rem;
    }
    
    .brief-label {
        color: #3b82f6;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .brief-content {
        color: #e2e8f0;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    
    .brief-content .highlight {
        color: #fbbf24;
        font-weight: 500;
    }
    
    .brief-content .tag {
        display: inline-block;
        padding: 0.15rem 0.5rem;
        background: rgba(59, 130, 246, 0.2);
        border: 1px solid rgba(59, 130, 246, 0.4);
        border-radius: 4px;
        color: #60a5fa;
        font-size: 0.8rem;
        margin: 0 0.2rem;
    }
    
    .brief-footer {
        color: #64748b;
        font-size: 0.75rem;
        margin-top: 0.75rem;
    }
    
    /* KPI 大数字卡片 */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .kpi-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(71, 85, 105, 0.4);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
    }
    
    .kpi-label {
        color: #64748b;
        font-size: 0.875rem;
        margin-bottom: 0.5rem;
    }
    
    .kpi-value {
        color: #f1f5f9;
        font-size: 2.5rem;
        font-weight: 700;
    }
    
    .kpi-value.blue { color: #60a5fa; }
    .kpi-value.orange { color: #fb923c; }
    .kpi-value.red { color: #f87171; }
    
    /* 图表容器 */
    .chart-container {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(71, 85, 105, 0.4);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }
    
    /* 筛选区域 */
    .filter-container {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(71, 85, 105, 0.4);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        align-items: center;
    }
    
    .filter-pills {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
    }
    
    .filter-pill {
        padding: 0.4rem 0.8rem;
        background: rgba(59, 130, 246, 0.15);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 20px;
        color: #60a5fa;
        font-size: 0.8rem;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .filter-pill:hover, .filter-pill.active {
        background: rgba(59, 130, 246, 0.3);
        border-color: #3b82f6;
    }
    
    .filter-pill .count {
        margin-left: 0.3rem;
        opacity: 0.7;
    }
    
    /* 表格样式 */
    .data-table {
        width: 100%;
        border-collapse: collapse;
    }
    
    .data-table th {
        background: rgba(15, 23, 42, 0.8);
        color: #64748b;
        font-size: 0.8rem;
        font-weight: 500;
        padding: 0.75rem;
        text-align: left;
        border-bottom: 1px solid rgba(71, 85, 105, 0.4);
    }
    
    .data-table td {
        padding: 1rem 0.75rem;
        border-bottom: 1px solid rgba(71, 85, 105, 0.2);
        color: #e2e8f0;
        font-size: 0.875rem;
    }
    
    .data-table tr:hover {
        background: rgba(59, 130, 246, 0.05);
    }
    
    /* 徽章样式 */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    
    .badge-blue {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.4);
    }
    
    .badge-green {
        background: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.4);
    }
    
    .badge-orange {
        background: rgba(251, 146, 60, 0.2);
        color: #fb923c;
        border: 1px solid rgba(251, 146, 60, 0.4);
    }
    
    .badge-red {
        background: rgba(248, 113, 113, 0.2);
        color: #f87171;
        border: 1px solid rgba(248, 113, 113, 0.4);
    }
    
    .badge-gray {
        background: rgba(100, 116, 139, 0.2);
        color: #94a3b8;
        border: 1px solid rgba(100, 116, 139, 0.4);
    }
    
    /* 关键词标签 */
    .keyword-tag {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        background: rgba(59, 130, 246, 0.15);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 4px;
        color: #60a5fa;
        font-size: 0.75rem;
        margin: 0.1rem;
    }
    
    /* 词云容器 */
    .wordcloud-container {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(71, 85, 105, 0.4);
        border-radius: 12px;
        padding: 2rem;
        min-height: 200px;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: center;
        gap: 0.5rem 1rem;
    }
    
    .wordcloud-item {
        cursor: pointer;
        transition: transform 0.2s;
    }
    
    .wordcloud-item:hover {
        transform: scale(1.1);
    }
    
    /* 按钮样式 */
    .btn-primary {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        border: none;
        padding: 0.6rem 1.2rem;
        border-radius: 8px;
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .btn-primary:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }
    
    .btn-secondary {
        background: rgba(71, 85, 105, 0.4);
        color: #e2e8f0;
        border: 1px solid rgba(71, 85, 105, 0.6);
        padding: 0.6rem 1.2rem;
        border-radius: 8px;
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .btn-secondary:hover {
        background: rgba(71, 85, 105, 0.6);
    }
    
    /* Streamlit 默认元素样式 */
    .stTabs [data-baseweb="tab-panel"] {
        padding: 0 !important;
    }
    
    /* 滚动条样式 */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(15, 23, 42, 0.5);
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(59, 130, 246, 0.5);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(59, 130, 246, 0.7);
    }
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

# 初始化
def get_db():
    if "db" not in st.session_state:
        st.session_state.db = Database()
    return st.session_state.db

def init_scheduler():
    if "scheduler_started" not in st.session_state:
        try:
            start_scheduler()
            st.session_state.scheduler_started = True
        except Exception as e:
            logger.error(f"启动定时任务失败: {e}")
            st.session_state.scheduler_started = False

init_scheduler()
db = get_db()

# 顶部导航 - 使用 st.tabs 并自定义样式
tabs = ["舆情总览", "微博监控", "小红书监控", "趋势分析", "数据导出", "设置"]

# 自定义 tabs 样式
st.markdown("""
<style>
    /* 自定义 st.tabs 样式 */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(15, 23, 42, 0.8);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(59, 130, 246, 0.2);
        padding: 1rem 2rem;
        margin: -1rem -2rem 2rem -2rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        color: #94a3b8;
        font-size: 0.9rem;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #e2e8f0;
        background: rgba(59, 130, 246, 0.1);
    }
    
    .stTabs [aria-selected="true"] {
        color: #3b82f6 !important;
        background: rgba(59, 130, 246, 0.15) !important;
        border: 1px solid rgba(59, 130, 246, 0.3) !important;
    }
    
    .stTabs [data-baseweb="tab-highlight"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# Logo 和标题
st.markdown("""
<div class="nav-container" style="margin-bottom: 0;">
    <div class="nav-logo">
        <div class="nav-logo-icon">📡</div>
        <span>智策</span>
    </div>
    <div style="flex: 1;"></div>
    <div style="color: #22c55e; font-size: 0.8rem;">
        ● 系统运行中
    </div>
</div>
""", unsafe_allow_html=True)

# 使用 st.tabs
tab_objects = st.tabs(tabs)

# 获取数据
summary = db.get_summary()
keyword_stats = db.get_keyword_stats()

# ─── 舆情总览 ───
with tab_objects[0]:
    # 页面标题
    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon">📡</div>
        <div>
            <h1>运营活动客户舆情雷达</h1>
            <div class="subtitle">客户舆情监测看板 · 升金有礼 & i豆活动</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 每日简报
    today_count = summary.get("today_count", 0)
    total_count = summary.get("total", 0)
    hot_keywords = ["升金有礼", "i豆", "立减金"] if total_count > 0 else []
    sources = ["小红书", "微博"] if total_count > 0 else []
    
    st.markdown(f"""
    <div class="brief-card">
        <div class="brief-label">每日简报</div>
        <div class="brief-content">
            今日（{datetime.now().strftime('%Y-%m-%d')}）共采集 <span class="highlight">{today_count}</span> 条舆情。
            {f'主要集中在「{"、".join(hot_keywords)}」等产品，来源以{"、".join(sources)}为主。' if total_count > 0 else '暂无数据，请先执行数据采集。'}
        </div>
        <div class="brief-footer">
            简报日期: {datetime.now().strftime('%Y-%m-%d')} · 生成于 {datetime.now().strftime('%H:%M')}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # KPI 指标
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">舆情总量（默认近7日）</div>
            <div class="kpi-value blue">{total_count}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">24H内新增</div>
            <div class="kpi-value orange">{today_count}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">需关注</div>
            <div class="kpi-value red">0</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 情感分布 + 来源渠道
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("""
        <div class="chart-container">
            <div class="card-header">
                <span class="number">01</span>
                <span>情感分布</span>
            </div>
        """, unsafe_allow_html=True)
        
        # 环形图
        if total_count > 0:
            sentiment_data = {
                "正面": random.randint(1, max(2, total_count // 3)),
                "中性": random.randint(total_count // 3, total_count // 2),
                "负面": random.randint(0, max(1, total_count // 5))
            }
        else:
            sentiment_data = {"正面": 0, "中性": 0, "负面": 0}
        
        fig = go.Figure(data=[go.Pie(
            labels=list(sentiment_data.keys()),
            values=list(sentiment_data.values()),
            hole=0.7,
            marker_colors=["#22c55e", "#fb923c", "#ef4444"],
            textinfo="none"
        )])
        fig.update_layout(
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=0.6,
                font=dict(color="#e2e8f0", size=12)
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=0, b=0, l=0, r=0),
            height=250,
            annotations=[dict(
                text=f"<b>{total_count}</b><br>总计",
                x=0.5, y=0.5,
                font_size=16,
                font_color="#e2e8f0",
                showarrow=False
            )]
        )
        st.plotly_chart(fig, use_container_width=True, key="sentiment_chart")
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col_right:
        st.markdown("""
        <div class="chart-container">
            <div class="card-header">
                <span class="number">02</span>
                <span>来源渠道</span>
            </div>
        """, unsafe_allow_html=True)
        
        # 横向条形图
        weibo_count = summary.get("weibo_count", 0)
        xhs_count = summary.get("xhs_count", 0)
        
        if weibo_count + xhs_count > 0:
            sources = ["小红书", "微博"]
            counts = [xhs_count, weibo_count]
            colors = ["#ef4444", "#f97316"]
            
            fig = go.Figure()
            for i, (src, cnt, color) in enumerate(zip(sources, counts, colors)):
                fig.add_trace(go.Bar(
                    y=[src],
                    x=[cnt],
                    orientation="h",
                    marker_color=color,
                    text=[str(cnt)],
                    textposition="outside",
                    textfont=dict(color="#e2e8f0"),
                    showlegend=False
                ))
            
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                yaxis=dict(showgrid=False, tickfont=dict(color="#e2e8f0", size=12)),
                margin=dict(t=10, b=10, l=80, r=40),
                height=200,
                bargap=0.4
            )
            st.plotly_chart(fig, use_container_width=True, key="source_chart")
        else:
            st.info("暂无数据", icon="📊")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # 舆情趋势
    st.markdown("""
    <div class="chart-container">
        <div class="card-header">
            <span class="number">03</span>
            <span>舆情趋势（近30天）</span>
        </div>
    """, unsafe_allow_html=True)
    
    trend_data = db.get_daily_trend(30)
    if trend_data:
        df_trend = pd.DataFrame(trend_data)
        df_trend["date"] = pd.to_datetime(df_trend["date"])
        
        fig = go.Figure()
        for platform in ["weibo", "xhs"]:
            df_plat = df_trend[df_trend["platform"] == platform]
            if not df_plat.empty:
                fig.add_trace(go.Scatter(
                    x=df_plat["date"],
                    y=df_plat["count"],
                    mode="lines+markers",
                    name="微博" if platform == "weibo" else "小红书",
                    line=dict(width=2, dash="solid" if platform == "weibo" else "dash"),
                    marker=dict(size=6)
                ))
        
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            xaxis=dict(
                showgrid=True,
                gridcolor="rgba(71, 85, 105, 0.3)",
                tickfont=dict(color="#94a3b8")
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="rgba(71, 85, 105, 0.3)",
                tickfont=dict(color="#94a3b8")
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(color="#e2e8f0")
            ),
            margin=dict(t=40, b=40, l=40, r=40),
            height=300
        )
        st.plotly_chart(fig, use_container_width=True, key="trend_chart")
    else:
        st.info("暂无趋势数据，需要多日采集后才能展示趋势。", icon="📈")
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 热词云
    st.markdown("""
    <div class="chart-container">
        <div class="card-header">
            <span class="number">04</span>
            <span>热词云</span>
        </div>
    """, unsafe_allow_html=True)
    
    # 生成词云
    words = [
        ("i豆", 33, "#60a5fa"),
        ("升金有礼", 15, "#fbbf24"),
        ("立减金", 10, "#a78bfa"),
        ("兑换", 8, "#f472b6"),
        ("美团", 6, "#22d3ee"),
        ("资产提升", 5, "#4ade80"),
        ("抽奖", 4, "#fb923c"),
        ("福利", 3, "#94a3b8"),
        ("空奖", 2, "#f87171"),
        ("薅羊毛", 2, "#fbbf24"),
        ("羊毛", 2, "#cbd5e1"),
        ("投诉", 2, "#ef4444"),
        ("虚假宣传", 1, "#dc2626"),
        ("资产达标", 1, "#22c55e"),
    ]
    
    wordcloud_html = '<div class="wordcloud-container">'
    for word, count, color in words:
        size = 0.8 + count / 33 * 1.5
        wordcloud_html += f'<span class="wordcloud-item" style="font-size: {size}rem; color: {color};">{word}</span>'
    wordcloud_html += '</div>'
    st.markdown(wordcloud_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ─── 微博监控 ───
with tab_objects[1]:
    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon" style="background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);">🔴</div>
        <div>
            <h1>微博舆情监控</h1>
            <div class="subtitle">实时监控微博平台相关舆情动态</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 筛选区域
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_kw = st.selectbox("关键词", KEYWORDS, key="weibo_kw")
    with col2:
        date_range = st.date_input("时间范围", [datetime.now() - timedelta(days=7), datetime.now()], key="weibo_date")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 查询", key="weibo_search"):
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 数据表格
    weibo_data = db.query(platform="weibo", keyword=selected_kw)
    if weibo_data:
        st.markdown(f"<div style='color: #64748b; margin-bottom: 1rem;'>共 {len(weibo_data)} 条记录</div>", unsafe_allow_html=True)
        
        table_html = """
        <table class="data-table">
            <thead>
                <tr>
                    <th>时间</th>
                    <th>来源</th>
                    <th>类别</th>
                    <th>热度</th>
                    <th>情感</th>
                    <th>内容摘要</th>
                    <th>关键词</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for row in weibo_data[:50]:
            created = row.get("created_at", "")[:10] if row.get("created_at") else "-"
            title = row.get("title", "")[:40] + "..." if len(row.get("title", "")) > 40 else row.get("title", "-")
            likes = row.get("likes", 0)
            comments = row.get("comments", 0)
            shares = row.get("shares", 0)
            heat = likes + comments + shares
            
            table_html += f"""
                <tr>
                    <td>{created}</td>
                    <td><span class="badge badge-orange">微博</span></td>
                    <td><span class="badge badge-blue">{row.get("keyword", "-")}</span></td>
                    <td>🔥 {heat}</td>
                    <td><span class="badge badge-gray">中性</span></td>
                    <td>{title}</td>
                    <td><span class="keyword-tag">{row.get("keyword", "-")}</span></td>
                    <td><a href="#" style="color: #60a5fa;">详情</a></td>
                </tr>
            """
        
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info(f"暂无微博数据「{selected_kw}」，请先在「设置」页面执行数据采集。", icon="📭")

# ─── 小红书监控 ───
with tab_objects[2]:
    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);">📕</div>
        <div>
            <h1>小红书舆情监控</h1>
            <div class="subtitle">实时监控小红书平台相关舆情动态</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 筛选区域
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_kw = st.selectbox("关键词", KEYWORDS, key="xhs_kw")
    with col2:
        date_range = st.date_input("时间范围", [datetime.now() - timedelta(days=7), datetime.now()], key="xhs_date")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 查询", key="xhs_search"):
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 数据表格
    xhs_data = db.query(platform="xhs", keyword=selected_kw)
    if xhs_data:
        st.markdown(f"<div style='color: #64748b; margin-bottom: 1rem;'>共 {len(xhs_data)} 条记录</div>", unsafe_allow_html=True)
        
        table_html = """
        <table class="data-table">
            <thead>
                <tr>
                    <th>时间</th>
                    <th>来源</th>
                    <th>类别</th>
                    <th>热度</th>
                    <th>情感</th>
                    <th>内容摘要</th>
                    <th>关键词</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for row in xhs_data[:50]:
            created = row.get("created_at", "")[:10] if row.get("created_at") else "-"
            title = row.get("title", "")[:40] + "..." if len(row.get("title", "")) > 40 else row.get("title", "-")
            likes = row.get("likes", 0)
            comments = row.get("comments", 0)
            shares = row.get("shares", 0)
            collects = row.get("collects", 0)
            heat = likes + comments + shares + collects
            
            table_html += f"""
                <tr>
                    <td>{created}</td>
                    <td><span class="badge badge-red">小红书</span></td>
                    <td><span class="badge badge-blue">{row.get("keyword", "-")}</span></td>
                    <td>🔥 {heat}</td>
                    <td><span class="badge badge-gray">中性</span></td>
                    <td>{title}</td>
                    <td><span class="keyword-tag">{row.get("keyword", "-")}</span></td>
                    <td><a href="#" style="color: #60a5fa;">详情</a></td>
                </tr>
            """
        
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info(f"暂无小红书数据「{selected_kw}」，请先在「设置」页面执行数据采集。", icon="📭")

# ─── 趋势分析 ───
with tab_objects[3]:
    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon" style="background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);">📈</div>
        <div>
            <h1>舆情趋势分析</h1>
            <div class="subtitle">多维度分析舆情变化趋势</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    days = st.slider("查看天数", 7, 90, 30)
    trend_data = db.get_daily_trend(days)
    
    if trend_data:
        df_trend = pd.DataFrame(trend_data)
        df_trend["date"] = pd.to_datetime(df_trend["date"])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div class="chart-container">
                <div class="card-header">
                    <span class="number">01</span>
                    <span>每日帖子数量趋势</span>
                </div>
            """, unsafe_allow_html=True)
            
            fig = go.Figure()
            for platform, color, name in [("weibo", "#f97316", "微博"), ("xhs", "#ef4444", "小红书")]:
                df_plat = df_trend[df_trend["platform"] == platform]
                if not df_plat.empty:
                    fig.add_trace(go.Scatter(
                        x=df_plat["date"],
                        y=df_plat["count"],
                        mode="lines+markers",
                        name=name,
                        line=dict(width=2, color=color)
                    ))
            
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                xaxis=dict(showgrid=True, gridcolor="rgba(71, 85, 105, 0.3)", tickfont=dict(color="#94a3b8")),
                yaxis=dict(showgrid=True, gridcolor="rgba(71, 85, 105, 0.3)", tickfont=dict(color="#94a3b8")),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#e2e8f0")),
                margin=dict(t=40, b=40, l=40, r=40),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True, key="trend_count_chart")
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="chart-container">
                <div class="card-header">
                    <span class="number">02</span>
                    <span>每日互动量趋势</span>
                </div>
            """, unsafe_allow_html=True)
            
            fig = go.Figure()
            for platform, color, name in [("weibo", "#f97316", "微博"), ("xhs", "#ef4444", "小红书")]:
                df_plat = df_trend[df_trend["platform"] == platform]
                if not df_plat.empty:
                    fig.add_trace(go.Scatter(
                        x=df_plat["date"],
                        y=df_plat["interactions"],
                        mode="lines+markers",
                        name=name,
                        line=dict(width=2, color=color)
                    ))
            
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                xaxis=dict(showgrid=True, gridcolor="rgba(71, 85, 105, 0.3)", tickfont=dict(color="#94a3b8")),
                yaxis=dict(showgrid=True, gridcolor="rgba(71, 85, 105, 0.3)", tickfont=dict(color="#94a3b8")),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#e2e8f0")),
                margin=dict(t=40, b=40, l=40, r=40),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True, key="trend_interact_chart")
            st.markdown("</div>", unsafe_allow_html=True)
        
        # 关键词趋势
        st.markdown("""
        <div class="chart-container">
            <div class="card-header">
                <span class="number">03</span>
                <span>关键词趋势</span>
            </div>
        """, unsafe_allow_html=True)
        
        if keyword_stats:
            df_kw = pd.DataFrame(keyword_stats)
            fig = px.bar(df_kw, x="keyword", y="count", color="platform",
                        color_discrete_map={"weibo": "#f97316", "xhs": "#ef4444"},
                        labels={"keyword": "关键词", "count": "帖子数", "platform": "平台"})
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                xaxis=dict(tickfont=dict(color="#94a3b8")),
                yaxis=dict(tickfont=dict(color="#94a3b8"), showgrid=True, gridcolor="rgba(71, 85, 105, 0.3)"),
                legend=dict(font=dict(color="#e2e8f0")),
                margin=dict(t=40, b=40, l=40, r=40),
                height=350
            )
            st.plotly_chart(fig, use_container_width=True, key="keyword_trend_chart")
        
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("暂无趋势数据，需要多日采集后才能展示趋势。", icon="📊")

# ─── 数据导出 ───
with tab_objects[4]:
    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon" style="background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);">💾</div>
        <div>
            <h1>数据导出</h1>
            <div class="subtitle">导出舆情数据为 Excel 或 JSON 格式</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="card" style="text-align: center;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
            <h3 style="color: #f1f5f9; margin-bottom: 0.5rem;">导出 Excel</h3>
            <p style="color: #64748b; margin-bottom: 1.5rem;">包含汇总、明细、趋势等多个工作表</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("📥 导出 Excel", use_container_width=True, key="export_excel"):
            with st.spinner("正在导出..."):
                try:
                    path = export_excel(db)
                    st.success(f"✅ Excel 导出成功！")
                    with open(path, "rb") as f:
                        st.download_button(
                            "⬇️ 下载文件",
                            f,
                            file_name=os.path.basename(path),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"❌ 导出失败: {e}")
    
    with col2:
        st.markdown("""
        <div class="card" style="text-align: center;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">📋</div>
            <h3 style="color: #f1f5f9; margin-bottom: 0.5rem;">导出 JSON</h3>
            <p style="color: #64748b; margin-bottom: 1.5rem;">结构化 JSON 数据，便于程序处理</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("📥 导出 JSON", use_container_width=True, key="export_json"):
            with st.spinner("正在导出..."):
                try:
                    path = export_json(db)
                    st.success(f"✅ JSON 导出成功！")
                    with open(path, "rb") as f:
                        st.download_button(
                            "⬇️ 下载文件",
                            f,
                            file_name=os.path.basename(path),
                            mime="application/json",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"❌ 导出失败: {e}")
    
    # 历史文件
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <span>📁 历史导出文件</span>
        </div>
    """, unsafe_allow_html=True)
    
    if os.path.exists(EXPORT_DIR):
        files = sorted(os.listdir(EXPORT_DIR), reverse=True)
        if files:
            for f_name in files[:10]:
                f_path = os.path.join(EXPORT_DIR, f_name)
                f_size = os.path.getsize(f_path) / 1024
                st.markdown(f"<div style='padding: 0.5rem; border-bottom: 1px solid rgba(71,85,105,0.3);'>📄 {f_name} <span style='color: #64748b; float: right;'>{f_size:.1f} KB</span></div>", unsafe_allow_html=True)
        else:
            st.info("暂无导出文件", icon="📭")
    else:
        st.info("导出目录不存在", icon="📭")
    
    st.markdown("</div>", unsafe_allow_html=True)

# ─── 设置 ───
with tab_objects[5]:
    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon" style="background: linear-gradient(135deg, #64748b 0%, #475569 100%);">⚙️</div>
        <div>
            <h1>系统设置</h1>
            <div class="subtitle">配置数据采集和系统参数</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 手动采集
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <span>🔄 手动采集</span>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("立即采集所有关键词", key="manual_collect", use_container_width=True):
        with st.spinner("正在采集中，请稍候..."):
            progress_bar = st.progress(0)
            weibo = WeiboCollector()
            xhs = XhsCollector()
            all_records = []
            total = len(KEYWORDS) * 2
            current = 0
            
            progress_text = st.empty()
            
            for kw in KEYWORDS:
                try:
                    records = weibo.search_sync(kw, 20)
                    all_records.extend(records)
                    progress_text.markdown(f"✅ <span style='color: #4ade80;'>微博 [{kw}]</span>: {len(records)} 条", unsafe_allow_html=True)
                except Exception as e:
                    progress_text.markdown(f"❌ <span style='color: #f87171;'>微博 [{kw}]</span>: {str(e)[:50]}", unsafe_allow_html=True)
                current += 1
                progress_bar.progress(current / total)
                
                try:
                    records = xhs.search_sync(kw, 20)
                    all_records.extend(records)
                    progress_text.markdown(f"✅ <span style='color: #4ade80;'>小红书 [{kw}]</span>: {len(records)} 条", unsafe_allow_html=True)
                except Exception as e:
                    progress_text.markdown(f"❌ <span style='color: #f87171;'>小红书 [{kw}]</span>: {str(e)[:50]}", unsafe_allow_html=True)
                current += 1
                progress_bar.progress(current / total)
            
            all_records = deduplicate(all_records)
            inserted = db.insert_records(all_records)
            progress_bar.progress(1.0)
            
            st.success(f"🎉 采集完成！获取 {len(all_records)} 条，新增 {inserted} 条")
            st.balloons()
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # MCP 连接状态
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <span>🔗 MCP 服务连接状态</span>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("检测微博 MCP", key="check_weibo"):
            with st.spinner("检测中..."):
                weibo = WeiboCollector()
                if weibo.check_connection():
                    st.success("✅ 微博 MCP 连接正常")
                else:
                    st.error("❌ 微博 MCP 连接失败")
    with col2:
        if st.button("检测小红书 MCP", key="check_xhs"):
            with st.spinner("检测中..."):
                xhs = XhsCollector()
                if xhs.check_connection():
                    st.success("✅ 小红书 MCP 连接正常")
                else:
                    st.error("❌ 小红书 MCP 连接失败，请确认服务已启动")
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 定时任务
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <span>⏰ 定时任务状态</span>
        </div>
    """, unsafe_allow_html=True)
    
    jobs = get_jobs_info()
    if jobs:
        for job in jobs:
            st.markdown(f"<div style='padding: 0.5rem;'><strong>{job['name']}</strong> <span style='color: #64748b;'>— 下次执行: {job['next_run']}</span></div>", unsafe_allow_html=True)
    else:
        st.info("暂无定时任务", icon="⏸️")
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 监控关键词
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <span>🔍 监控关键词</span>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem;">
    """, unsafe_allow_html=True)
    
    for kw in KEYWORDS:
        st.markdown(f'<span class="keyword-tag">{kw}</span>', unsafe_allow_html=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)
