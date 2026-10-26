"""AI Programming Tutor V2: dashboard entry point and explicit navigation."""
import html

import streamlit as st

from services.activity_service import build_heatmap, load_activities, summarize_activity
from services.problem_service import CatalogError, get_learning_route, load_problems
from utils.ui import configure_page, render_heatmap


def open_practice(problem_id):
    st.session_state["requested_problem_id"] = problem_id
    st.switch_page("pages/practice.py")


def dashboard():
    st.markdown('<div class="eyebrow">YOUR ALGORITHM JOURNEY · V2.0</div>', unsafe_allow_html=True)
    st.title("把每一次练习，变成进步。")
    st.caption("选一道题，写下思路，再向前走一步。学习进度来自你保存的本地刷题活动。")
    try:
        problems = load_problems()
        route = get_learning_route()
    except CatalogError as exc:
        st.error(f"题库加载失败：{exc}")
        st.caption("请修复 data/problem_catalog.json 后刷新页面。学习记录和本地提交未受影响。")
        st.stop()
    try:
        activities = load_activities()
        summary = summarize_activity(activities, problems)
    except (OSError, ValueError) as exc:
        activities, summary = None, None
        st.error("无法读取刷题活动，请检查活动文件格式和读取权限。原数据未被覆盖。")

    metrics = st.columns(4)
    values = (
        summary["total_submissions"] if summary else "—",
        summary["completed_problems"] if summary else "—",
        summary["streak_days"] if summary else "—",
        f"第 {summary['recommended_stage']} 阶段" if summary else "—",
    )
    for column, label, value in zip(metrics, ("累计刷题提交", "已完成 LeetCode 题目", "连续学习天数", "推荐学习阶段"), values):
        column.metric(label, value)
    st.caption("提交仅统计「记录一次本地提交」；完成数仅统计你确认在 LeetCode 通过的不同题目。AI 诊断不会增加这两项。")

    st.subheader("学习活动", divider="green")
    if activities is not None:
        render_heatmap(build_heatmap(activities))
        if not summary["total_submissions"]:
            st.info("还没有本地刷题提交。开始练习后，点击「记录一次本地提交」点亮第一格。")
    else:
        st.warning("活动数据暂不可用，恢复读取后再生成绿墙。")
    st.caption("过去 365 天 · 按北京时间归日。今天尚未提交时，连续天数可延续至昨天；仅确认通过不会点亮绿墙。")

    st.subheader("推荐刷题路线", divider="green")
    completed = summary["completed_ids"] if summary else set()
    recommended = summary["recommended_stage"] if summary else 1
    stage_problems = [p for p in problems if p["stage"] == recommended]
    next_problem = next((p for p in stage_problems if p["id"] not in completed), None)
    if next_problem is None and stage_problems:
        next_problem = stage_problems[0]
    if all(p["id"] in completed for p in problems):
        st.success("当前精选题库已全部完成！可以从动态规划阶段开始复习，或选择其他题目巩固。")
    if next_problem is not None:
        if st.button("开始推荐练习", type="primary", key="start_recommended"):
            open_practice(next_problem["id"])
    else:
        st.info("当前推荐阶段暂无题目，请查看下方其他阶段或补充题库。")
    st.caption("按基础到进阶逐步推进；阶段内题目全部标记通过后，推荐下一未完成阶段。通过状态为用户自报。")
    for stage in route:
        done = sum(p["id"] in completed for p in stage["problems"])
        label = f"{stage['id']:02d} · {stage['title']}　{done}/{len(stage['problems'])} 已完成"
        with st.expander(label, expanded=stage["id"] == recommended):
            for problem in stage["problems"]:
                title, meta, action = st.columns([3.4, 2.1, 1.2], vertical_alignment="center")
                title.markdown(f"**#{problem['id']} · {html.escape(problem['title_zh'])}**")
                title.caption(problem["title_en"] + " · " + " / ".join(problem["tags"]))
                status = "已通过（用户自报）" if problem["id"] in completed else "待练习"
                meta.caption(f"{problem['difficulty']} · {status}")
                if action.button("进入练习", key=f"route_{problem['id']}", use_container_width=True):
                    open_practice(problem["id"])


configure_page()
with st.sidebar:
    st.markdown("### ◈ AI Programming Tutor")
    st.caption("V2.0 · 练习 / 反思 / 进步")

navigation = st.navigation([
    st.Page(dashboard, title="学习仪表盘", icon="📊", default=True),
    st.Page("pages/practice.py", title="选题与练习", icon="💻", url_path="practice"),
    st.Page("pages/history.py", title="学习记录", icon="📚", url_path="history"),
])
navigation.run()
