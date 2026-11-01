"""Shared visual theme and read-only activity calendar.

Keep application styling here so page layouts can evolve independently.
"""

from datetime import date, timedelta
from html import escape

import streamlit as st


THEME_CSS = """
<style>
:root {
  --tutor-bg: #0b1020;
  --tutor-card: #131d31;
  --tutor-border: #29374e;
  --tutor-text: #edf4ff;
  --tutor-muted: #9cadc6;
  --tutor-accent: #51d09a;
}
.stApp { background: var(--tutor-bg); color: var(--tutor-text); }
[data-testid="stSidebar"] { background: #10182a; border-right: 1px solid var(--tutor-border); }
[data-testid="stMainBlockContainer"] { max-width: 1680px; padding: 1rem 1rem 2rem !important; }
@media (min-width: 1200px) {
  [data-testid="stSidebar"] { width: 250px !important; min-width: 250px !important; max-width: 250px !important; }
  [data-testid="stSidebarContent"] { width: 250px !important; }
}
[data-testid="stMetric"] {
  background: var(--tutor-card); border: 1px solid var(--tutor-border);
  border-radius: 14px; padding: 1rem 1.2rem;
}
[data-testid="stMetricLabel"] { color: var(--tutor-muted); }
.stButton > button { border-radius: 9px; }
.hero {
  padding: 1.6rem 1.8rem; margin: .2rem 0 1.4rem;
  border: 1px solid #29483f; border-radius: 18px;
  background: linear-gradient(110deg, #13283a, #122131 70%, #102c27);
}
.hero h1 { margin: .25rem 0 .5rem; font-size: clamp(1.8rem, 4vw, 2.5rem); }
.hero p { margin: .4rem 0; color: #bed0e3; }
.eyebrow { color: var(--tutor-accent); font-size: .78rem; letter-spacing: .12em; font-weight: 700; }
.workspace-topbar { display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; margin: 0 0 .7rem; }
.workspace-kicker { color: var(--tutor-accent); font-size: .7rem; letter-spacing: .12em; font-weight: 700; }
.workspace-title { margin: .12rem 0 0; font-size: 1.55rem; line-height: 1.15; letter-spacing: -.015em; color: var(--tutor-text); }
.workspace-topnote { color: var(--tutor-muted); font-size: .76rem; padding-bottom: .15rem; }
[data-testid="stMainBlockContainer"] h2 { margin-top: .1rem; margin-bottom: .15rem; }
[data-testid="stMainBlockContainer"] h1:not(.workspace-title) { margin-top: .5rem; }
.problem-summary { color: #c6d6e8; font-size: .88rem; line-height: 1.6; margin: .1rem 0 .3rem; }
.editor-meta { color: var(--tutor-muted); font-size: .78rem; }
[data-testid="stExpander"] { border-color: var(--tutor-border); border-radius: 10px; }
[data-testid="stExpander"] summary { padding: .35rem .75rem; font-size: .84rem; }
.muted, .problem-meta, .caption { color: var(--tutor-muted); font-size: .9rem; }
.stage-card { border: 1px solid var(--tutor-border); background: var(--tutor-card); border-radius: 14px; padding: 1rem 1.25rem; }
.stage-card h3 { margin: 0 0 .4rem; }
.tutor-heatmap { border: 1px solid var(--tutor-border); border-radius: 14px; background: var(--tutor-card); padding: 1.2rem; }
.tutor-heatmap p { margin: 0 0 .85rem; color: var(--tutor-muted); font-size: .88rem; }
.tutor-calendar-scroll { overflow-x: auto; padding-bottom: .4rem; }
.tutor-calendar { width: max-content; }
.tutor-months { display: grid; gap: 4px; margin: 0 0 5px 30px; height: 19px; color: var(--tutor-muted); font-size: 10px; }
.tutor-months span { white-space: nowrap; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.tutor-calendar-body { display: flex; align-items: flex-start; }
.tutor-weekdays { width: 30px; display: grid; grid-template-rows: repeat(7, 12px); gap: 4px; color: var(--tutor-muted); font-size: 10px; }
.tutor-days { display: grid; grid-auto-flow: column; grid-template-rows: repeat(7, 12px); grid-auto-columns: 12px; gap: 4px; }
.tutor-day, .tutor-legend-cell { display: block; width: 12px; height: 12px; border: 1px solid #ffffff10; border-radius: 3px; box-sizing: border-box; }
.tutor-day:hover { outline: 2px solid #d7e7ff; outline-offset: 1px; }
.tutor-day:focus-visible { outline: 2px solid #d7e7ff; outline-offset: 1px; }
.tutor-day.level-0, .tutor-legend-cell.level-0 { background: #253247; }
.tutor-day.level-1, .tutor-legend-cell.level-1 { background: #155c44; }
.tutor-day.level-2, .tutor-legend-cell.level-2 { background: #20885b; }
.tutor-day.level-3, .tutor-legend-cell.level-3 { background: #35b676; }
.tutor-day.level-4, .tutor-legend-cell.level-4 { background: #70e2a0; }
.tutor-day.empty { visibility: hidden; }
.tutor-legend { display: flex; justify-content: flex-end; align-items: center; gap: 6px; margin-top: .8rem; color: var(--tutor-muted); font-size: .75rem; }
.problem-badges { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: .15rem 0 .4rem; }
.difficulty-badge, .workspace-chip {
  display: inline-block; padding: .16rem .55rem; border-radius: 999px;
  border: 1px solid var(--tutor-border); font-size: .75rem; font-weight: 600; letter-spacing: .03em;
}
.difficulty-badge.easy { color: #7fe6b6; background: #10382a; border-color: #1f6a50; }
.difficulty-badge.medium { color: #f6cf72; background: #3a2c10; border-color: #7a5f22; }
.difficulty-badge.hard { color: #ff9f9f; background: #3b171b; border-color: #7d3038; }
.workspace-chip { color: #b9c9df; background: #17243a; }
.problem-en { color: var(--tutor-muted); font-size: .85rem; margin-left: .35rem; }
.toolbar-label { color: var(--tutor-muted); font-size: .76rem; letter-spacing: .1em; text-transform: uppercase; margin: .2rem 0 .4rem; }
[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: var(--tutor-border) !important; border-radius: 14px;
  background: rgba(19, 29, 49, .62);
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] { background: transparent; }
.diagnosis-block {
  border-left: 3px solid #2f8f6b; border-radius: 0 8px 8px 0;
  padding: .45rem .8rem .5rem; margin: .25rem 0 .8rem;
  background: linear-gradient(90deg, rgba(21, 56, 43, .55), rgba(19, 29, 49, 0));
}
.diagnosis-label { color: var(--tutor-muted); font-size: .76rem; letter-spacing: .08em; text-transform: uppercase; margin: .5rem 0 .2rem; }
.diagnosis-value { color: var(--tutor-text); font-size: 1rem; font-weight: 600; margin-top: .1rem; }
.empty-panel {
  border: 1px dashed var(--tutor-border); border-radius: 12px;
  padding: 1rem 1.1rem; color: var(--tutor-muted); background: #0f1728; line-height: 1.7;
}
.empty-kicker { color: var(--tutor-accent); font-size: .68rem; letter-spacing: .12em; font-weight: 700; text-transform: uppercase; margin-bottom: .4rem; }
.empty-panel strong { display: block; color: var(--tutor-text); font-size: 1.02rem; margin-bottom: .35rem; }
.empty-panel p { margin: .4rem 0; }
.empty-preview { margin: .7rem 0 .55rem; border-top: 1px solid var(--tutor-border); padding-top: .65rem; }
.preview-title { color: var(--tutor-muted); font-size: .68rem; letter-spacing: .1em; text-transform: uppercase; margin-bottom: .3rem; }
.preview-row {
  display: flex; align-items: center; justify-content: space-between; gap: .6rem;
  padding: .34rem 0; border-bottom: 1px dashed #22314a; color: #bacbe0; font-size: .8rem;
}
.preview-row:last-child { border-bottom: 0; }
.preview-pending { color: #6f839e; font-size: .72rem; }
.empty-note { color: var(--tutor-muted); font-size: .78rem; }
.results-head {
  display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem;
  margin: 1.3rem 0 .55rem; padding-top: .85rem; border-top: 1px solid var(--tutor-border);
}
.results-head h3 { margin: .08rem 0 0; font-size: 1.05rem; color: var(--tutor-text); }
.results-note { color: var(--tutor-muted); font-size: .76rem; }
.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .7rem; }
.status-card {
  border: 1px solid var(--tutor-border); border-radius: 12px;
  background: var(--tutor-card); padding: .8rem .95rem;
}
.status-label { color: var(--tutor-muted); font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; }
.status-value { color: var(--tutor-text); font-size: 1.12rem; font-weight: 700; margin: .25rem 0 .15rem; }
.status-value.ok { color: var(--tutor-accent); }
.status-value.warn { color: #f6cf72; }
.status-note { color: var(--tutor-muted); font-size: .76rem; line-height: 1.5; }
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #2fae7c, #51d09a); color: #06281c;
  border: 0; font-weight: 700;
}
.stButton > button[kind="primary"]:hover { filter: brightness(1.08); }
.stButton > button[kind="secondary"] {
  background: #16233a; border: 1px solid var(--tutor-border); color: var(--tutor-text);
}
.stApp, .stApp input, .stApp textarea {
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, sans-serif;
}
.stApp code, .stApp pre, [data-testid="stCode"] {
  font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
}
@media (max-width: 900px) {
  .workspace-topbar { align-items: flex-start; flex-direction: column; gap: .2rem; }
  .workspace-topnote { padding-bottom: 0; }
}
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-top: 1rem; }
  .hero { padding: 1.1rem; }
  .tutor-heatmap { padding: .85rem; }
  .status-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .problem-en { width: 100%; margin-left: 0; }
  .results-head { align-items: flex-start; flex-direction: column; gap: .15rem; }
}
</style>
"""


def configure_page(title="AI Programming Tutor"):
    st.set_page_config(page_title=title, page_icon="🧠", layout="wide", initial_sidebar_state="expanded")
    st.html(THEME_CSS)


def build_heatmap_html(cells):
    """Return an escaped calendar using only the supplied actual activity counts.

    Missing dates and leading/trailing week padding stay blank. Input counts
    represent local submissions; acceptance confirmations are not inferred here.
    """
    days = {}
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        try:
            day = date.fromisoformat(cell["date"])
        except (ValueError, TypeError, KeyError):
            continue
        count, level = cell.get("count", 0), cell.get("level", 0)
        count = count if type(count) is int and count >= 0 else 0
        level = level if type(level) is int and 0 <= level <= 4 else 0
        days[day] = (count, level)
    if not days:
        return '<div class="tutor-heatmap"><p>暂无可展示的活动日期。</p></div>'

    first, last = min(days), max(days)
    start = first - timedelta(days=first.weekday())
    total_cells = (last - start).days + 1
    total_cells += (-total_cells) % 7
    weeks = total_cells // 7
    tiles, month_starts = [], []
    previous_month = None
    for offset in range(total_cells):
        current = start + timedelta(days=offset)
        if current in days:
            count, level = days[current]
            title = escape(f"{current.isoformat()}：{count} 次本地刷题提交", quote=True)
            tiles.append(f'<span class="tutor-day level-{level}" role="img" title="{title}" aria-label="{title}"></span>')
            month = (current.year, current.month)
            if month != previous_month:
                month_starts.append((offset // 7, current.year, current.month))
                previous_month = month
        else:
            tiles.append('<span class="tutor-day empty" aria-hidden="true"></span>')
    # Reserve each month only its own columns. A short first/last partial month
    # may have insufficient room even for a short label; keep those columns blank.
    months = []
    for index, (column, year, month) in enumerate(month_starts):
        next_column = month_starts[index + 1][0] if index + 1 < len(month_starts) else weeks
        span = next_column - column
        available_width = span * 16 - 4  # 12px square plus 4px calendar gap.
        label = f"{year}年1月" if month == 1 else f"{month}月"
        if available_width < (54 if month == 1 else 24):
            continue
        title = escape(f"{year}年{month}月", quote=True)
        months.append(f'<span title="{title}" style="grid-column:{column + 1} / span {span}">{escape(label)}</span>')
    total = sum(count for count, _ in days.values())
    period = escape(f"{first.isoformat()} 至 {last.isoformat()} · {total} 次本地刷题提交")
    legend = ''.join(f'<span class="tutor-legend-cell level-{level}" title="{escape(label, quote=True)}"></span>'
                     for level, label in enumerate(("0 次", "1 次", "2 次", "3 次", "4 次及以上")))
    weekdays = ''.join(f'<span>{label}</span>' for label in ("一", "", "三", "", "五", "", "日"))
    return (
        f'<section class="tutor-heatmap" aria-label="{period}"><p>{period}</p>'
        '<div class="tutor-calendar-scroll"><div class="tutor-calendar">'
        f'<div class="tutor-months" style="grid-template-columns:repeat({weeks},12px)">{"".join(months)}</div>'
        f'<div class="tutor-calendar-body"><div class="tutor-weekdays" aria-hidden="true">{weekdays}</div>'
        f'<div class="tutor-days">{"".join(tiles)}</div></div></div></div>'
        f'<div class="tutor-legend"><span>少</span>{legend}<span>多</span></div></section>'
    )


def render_heatmap(cells):
    st.html(build_heatmap_html(cells))
