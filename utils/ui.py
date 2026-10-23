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
[data-testid="stMainBlockContainer"] { max-width: 1360px; padding-top: 2.2rem; padding-bottom: 3rem; }
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
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-top: 1rem; }
  .hero { padding: 1.1rem; }
  .tutor-heatmap { padding: .85rem; }
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
