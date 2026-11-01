"""Problem selection, split-pane workspace, session drafts, coaching, and explicit activities."""
from datetime import datetime, timedelta, timezone
from html import escape
from uuid import uuid4

import streamlit as st

from services.activity_service import load_activities, mark_accepted, problem_status, record_submission
from services.llm_service import DiagnosisError, analyze_code, normalize_diagnosis
from services.practice_service import (begin_diagnosis, clear_diagnosis, diagnosis_request_is_current,
                                       reveal_next_hint, save_draft, select_problem, set_diagnosis)
from services.problem_service import CatalogError, load_problems, search_problems
from services.record_service import save_record, update_record
from utils.editor import render_code_editor
from utils.draft_export import build_draft_export
from utils.ui import configure_page


def problem_badge_html(problem):
    tone = {"Easy": "easy", "Medium": "medium", "Hard": "hard"}.get(problem["difficulty"], "")
    tags = "".join(f'<span class="workspace-chip">{escape(tag)}</span>' for tag in problem["tags"])
    return (
        f'<div class="problem-badges"><span class="difficulty-badge {tone}">'
        f'{escape(problem["difficulty"])}</span>{tags}'
        f'<span class="problem-en">{escape(problem["title_en"])}</span></div>'
    )


def status_card(label, value, note, tone=""):
    return (
        f'<div class="status-card"><div class="status-label">{escape(label)}</div>'
        f'<div class="status-value {tone}">{escape(str(value))}</div>'
        f'<div class="status-note">{escape(note)}</div></div>'
    )


configure_page("代码练习 · AI Programming Tutor")
st.markdown(
    '<div class="workspace-topbar">'
    '<div><span class="workspace-kicker">AI PROGRAMMING TUTOR · V2.0</span>'
    '<h1 class="workspace-title">在线代码工作台</h1></div>'
    '<div class="workspace-topnote">精选题库 · 官方判题以 LeetCode 为准</div>'
    '</div>',
    unsafe_allow_html=True,
)

try:
    problems = load_problems()
except CatalogError as exc:
    st.error(f"题库加载失败：{exc}")
    st.caption("请修复 data/problem_catalog.json 后刷新页面。当前会话草稿与学习记录未受影响。")
    st.stop()
requested = st.session_state.pop("requested_problem_id", None)
if requested is not None:
    st.session_state["problem_search"] = ""
    st.session_state["difficulty_filter"] = "全部"
    st.session_state["tag_filter"] = []
    st.session_state["problem_picker"] = requested

filters = st.columns([2.6, 1, 2.2], gap="small", vertical_alignment="center")
query = filters[0].text_input("搜索题号或中英文题名", key="problem_search",
                              placeholder="搜索题号 / 中英文题名", label_visibility="collapsed")
level = filters[1].selectbox("难度", ["全部", "Easy", "Medium", "Hard"], key="difficulty_filter",
                             label_visibility="collapsed")
tags = filters[2].multiselect("算法标签", sorted({tag for p in problems for tag in p["tags"]}),
                              key="tag_filter", placeholder="算法标签（可多选）",
                              label_visibility="collapsed")
matches = search_problems(query=query, difficulty=None if level == "全部" else level, tags=tags)
if not matches:
    st.info("没有匹配题目，请调整搜索或筛选条件。已有草稿仍保留在当前会话中。")
    st.stop()

ids = [p["id"] for p in matches]
by_id = {p["id"]: p for p in problems}
if st.session_state.get("problem_picker") not in ids:
    preferred = st.session_state.get("selected_problem_id")
    st.session_state["problem_picker"] = preferred if preferred in ids else ids[0]
picker_cols = st.columns([3.3, 1], gap="small", vertical_alignment="center")
with picker_cols[0]:
    problem_id = st.selectbox(
        "选择题目", ids, key="problem_picker",
        format_func=lambda pid: f"#{pid} · {by_id[pid]['title_zh']} / {by_id[pid]['title_en']}",
        label_visibility="collapsed", help="选择题号后进入下方工作台。",
    )
picker_cols[1].caption(f"{len(matches)} 道题可练习")
problem = by_id[problem_id]
draft = select_problem(st.session_state, problem)
notice = st.session_state.pop("practice_notice", None)
if notice:
    st.success(notice)

left, right = st.columns([1.6, 1], gap="medium")

with left:
    head_left, head_right = st.columns([3.4, 1], gap="small", vertical_alignment="center")
    with head_left:
        st.subheader(f"#{problem_id:02d} · {problem['title_zh']}")
        st.markdown(problem_badge_html(problem), unsafe_allow_html=True)
    with head_right:
        st.link_button("LeetCode ↗", problem["official_url"], use_container_width=True,
                       help="打开 LeetCode 官方完整题面与正式判题页面。")

    st.markdown(f'<div class="problem-summary">{escape(problem["summary"])}</div>', unsafe_allow_html=True)
    with st.expander("示例与约束", expanded=False):
        for number, example in enumerate(problem["examples"], 1):
            st.markdown(f"**练习示例 {number}**")
            st.code(f"输入：{example['input']}\n输出：{example['output']}", language="text")
            if example.get("explanation"):
                st.caption(example["explanation"])
        st.markdown("**练习约束**")
        for constraint in problem["constraints"]:
            st.markdown(f"- {constraint}")
        st.caption(problem["source_note"])

    editor_opts = st.columns([1, 4], gap="small", vertical_alignment="center")
    with editor_opts[0]:
        st.selectbox("语言", ["Python 3"], key=f"language_{problem_id}",
                     label_visibility="collapsed", help="当前版本仅支持 Python 3。")
    editor_opts[1].markdown(
        '<span class="editor-meta">solution.py · 行号 / Python 语法高亮 / 自动缩进</span>',
        unsafe_allow_html=True,
    )

    editor_key = f"code_editor_{problem_id}"
    if editor_key not in st.session_state:
        st.session_state[editor_key] = draft
    code = render_code_editor(st.session_state[editor_key], key=editor_key)
    st.session_state[editor_key] = code
    save_draft(st.session_state, problem_id, code)

    st.caption("草稿按题独立保存，切题或切页后恢复；诊断会将当前题目与代码发送给 DeepSeek，可能产生费用。")
    with st.expander("导出当前会话草稿到新版工作台", expanded=False):
        st.caption("保留此页面会话，先下载草稿文件，再在新版工作台的草稿菜单中导入。导出不会修改代码或学习记录；新版已有草稿发生冲突时会保留已有内容。")
        st.download_button("下载全部草稿 JSON", data=build_draft_export(st.session_state),
                           file_name="ai-tutor-drafts.json", mime="application/json", key="export_session_drafts")

    diagnosis = st.session_state.get("diagnosis")
    has_diagnosis = diagnosis is not None and st.session_state.get("diagnosis_problem_id") == problem_id
    action_cols = st.columns([1, 1, 2.2], gap="small", vertical_alignment="center")
    with action_cols[0]:
        analyze_clicked = st.button(
            "重新诊断" if has_diagnosis else "AI 诊断（DeepSeek）",
            type="primary", key="diagnose", use_container_width=True,
        )
    with action_cols[1]:
        submit_clicked = st.button("记录本地提交", key="record_submission", use_container_width=True)
    action_cols[2].caption("提交只写入本地学习活动，不代表 LeetCode 通过。")

if analyze_clicked:
    if not code.strip():
        st.warning("请先填写代码，再开始诊断。")
    else:
        request = begin_diagnosis(st.session_state, problem_id, code)
        result = None
        failure = None
        try:
            with st.spinner("DeepSeek 正在分析当前题目与代码…"):
                result = normalize_diagnosis(analyze_code(code, problem))
        except DiagnosisError as error:
            failure = str(error)
        except Exception:
            # Do not expose upstream errors, request headers, or student source.
            failure = "诊断未能完成，请稍后重试。"
        if not diagnosis_request_is_current(st.session_state, request):
            st.info("题目、代码或诊断请求已更新，本次过时结果已丢弃。")
        elif result is None:
            clear_diagnosis(st.session_state)
            st.session_state["diagnosis_error"] = (
                (failure or "未获得有效的 DeepSeek 诊断结果。") + " 草稿已保留，未保存诊断记录。"
            )
        else:
            record_id = str(uuid4())
            record = {
                "question": f"#{problem_id} {problem['title_zh']}：{problem['summary']}",
                "error_type": result["error_type"], "knowledge": result["knowledge"], "hint_level": 1,
                "record_id": record_id, "leetcode_id": problem_id, "title": problem["title_zh"],
                "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "hints_used": [1], "is_mock": result["is_mock"],
                "source": result["source"], "model": result.get("model"),
            }
            try:
                save_record(record)
            except (OSError, ValueError, TypeError):
                record_id = None
                st.warning("诊断已完成，但诊断记录保存失败。请检查记录文件格式和写入权限。")
            set_diagnosis(st.session_state, problem_id, code, result, record_id)

diagnosis = st.session_state.get("diagnosis")
current_diagnosis = diagnosis if (
    st.session_state.get("diagnosis_problem_id") == problem_id
    and code == st.session_state.get("diagnosed_code")
) else None

with right:
    panel_height = 820 if current_diagnosis else 620
    with st.container(border=True, height=panel_height):
        diagnosis_error = st.session_state.pop("diagnosis_error", None)
        if diagnosis_error:
            st.error(diagnosis_error)
        if current_diagnosis:
            if current_diagnosis.get("source") == "deepseek":
                st.subheader("AI 诊断 · DeepSeek", divider="green")
                st.caption(f"来源：DeepSeek · 请求模型：{current_diagnosis.get('model', '未记录')} · "
                           "静态分析，未执行代码，不代表 LeetCode 判题结果。")
            else:
                st.subheader("辅导 · 本地规则 / Mock", divider="green")
                st.caption("来源：本地规则 / Mock；未调用真实大模型，未执行代码，不代表 LeetCode 判题结果。")
            st.markdown(
                f'<div class="diagnosis-block"><div class="diagnosis-label">错误类型</div>'
                f'<div class="diagnosis-value">{escape(str(current_diagnosis["error_type"]))}</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="diagnosis-block"><div class="diagnosis-label">涉及知识点</div>'
                f'<div class="diagnosis-value">{escape(str(current_diagnosis["knowledge"]))}</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="diagnosis-label">详细分析</div>', unsafe_allow_html=True)
            st.write(current_diagnosis["analysis"])
            st.markdown('<div class="diagnosis-label">三级渐进 Hint</div>', unsafe_allow_html=True)
            shown = st.session_state.get("hint_level", 1)
            for index, hint in enumerate(current_diagnosis["hints"][:shown], 1):
                st.info(f"Hint {index} · {hint}")
            if st.button("查看下一条 Hint", key="next_hint", use_container_width=True,
                         disabled=shown >= len(current_diagnosis["hints"])):
                shown = reveal_next_hint(st.session_state)
                record_id = st.session_state.get("diagnosis_record_id")
                if record_id:
                    try:
                        updated = update_record(record_id, {"hint_level": shown,
                                                            "hints_used": list(range(1, shown + 1))})
                        if not updated:
                            st.session_state["hint_save_warning"] = True
                    except (OSError, ValueError, TypeError):
                        st.session_state["hint_save_warning"] = True
                st.rerun()
            if st.session_state.pop("hint_save_warning", False):
                st.warning("Hint 已展示，但本次使用情况未能保存。")
        else:
            st.subheader("AI 诊断", divider="green")
            st.markdown(
                '<div class="empty-panel">'
                '<div class="empty-kicker">AI 辅导面板</div>'
                '<strong>还没有诊断结果</strong>'
                '<p>在左侧写下思路或代码，点击「AI 诊断（DeepSeek）」，'
                '结果会在这里按顺序展开。</p>'
                '<div class="empty-preview">'
                '<div class="preview-title">诊断面板将显示</div>'
                '<div class="preview-row"><span>错误类型</span>'
                '<span class="preview-pending">待生成</span></div>'
                '<div class="preview-row"><span>涉及知识点</span>'
                '<span class="preview-pending">待生成</span></div>'
                '<div class="preview-row"><span>详细分析</span>'
                '<span class="preview-pending">待生成</span></div>'
                '<div class="preview-row"><span>三级渐进 Hint</span>'
                '<span class="preview-pending">待生成</span></div>'
                '</div>'
                '<p class="empty-note">诊断只做静态分析，不会执行代码，也不代表 LeetCode 判题。</p>'
                '</div>',
                unsafe_allow_html=True,
            )

st.markdown(
    '<div class="results-head"><div><span class="workspace-kicker">STATUS</span>'
    '<h3>运行与提交</h3></div>'
    '<span class="results-note">本地学习状态 · 非 LeetCode 判题</span></div>',
    unsafe_allow_html=True,
)
try:
    activities = load_activities()
    problem_state = problem_status(activities, problem_id)
except (OSError, ValueError):
    problem_state = None
    st.error("无法读取本地活动。请检查活动文件，保存操作不会覆盖损坏数据。")

if problem_state is None:
    submission_count, accepted, last_submission = "—", False, None
else:
    submission_count = problem_state["submission_count"]
    accepted = problem_state["accepted"]
    last_submission = problem_state["last_submission_at"]
    if last_submission:
        last_submission = last_submission.replace("T", " ")[:16]

diagnosis_ready = current_diagnosis is not None
cards = "".join((
    status_card("代码执行", "未启用", "当前版本不包含安全的代码执行器"),
    status_card("示例测试", f"{len(problem['examples'])} 个示例", "仅作参考，未自动执行"),
    status_card("AI 诊断", "已生成" if diagnosis_ready else "未生成",
                "静态分析，不代表判题结果", "ok" if diagnosis_ready else ""),
    status_card("本地提交", submission_count, "主动记录，不等于 LeetCode 通过"),
    status_card("LeetCode 通过", "已通过（自报）" if accepted else "未确认",
                "用户自报状态", "ok" if accepted else "warn"),
))
st.markdown(f'<div class="status-grid">{cards}</div>', unsafe_allow_html=True)
st.caption("当前没有安全判题器，不会执行你的 Python 代码；示例仅作参考，"
           "本地提交不等于 LeetCode 通过。"
           f"最近一次本地提交：{last_submission or '暂无'}。")

with st.expander("查看本题示例与预期输出（参考，未执行）", expanded=False):
    for number, example in enumerate(problem["examples"], 1):
        st.markdown(f"**示例 {number}**")
        detail = f"输入：{example['input']}\n输出：{example['output']}"
        if example.get("explanation"):
            detail += f"\n说明：{example['explanation']}"
        st.code(detail, language="text")
    st.caption("以上为练习摘要中的示例，仅供对照；没有运行你的代码。")

accept_cols = st.columns([2.4, 1], vertical_alignment="center")
confirmed = accept_cols[0].checkbox(
    "我确认这道题已在 LeetCode 提交并通过（用户自报）", key=f"confirm_accepted_{problem_id}"
)
accept_clicked = accept_cols[1].button("记录 LeetCode 已通过", key="record_accepted",
                                       use_container_width=True, disabled=not confirmed or accepted)

if submit_clicked:
    if not code.strip():
        st.warning("请先填写代码，再记录本地提交。")
    else:
        try:
            fresh = current_diagnosis if code == st.session_state.get("diagnosed_code") else None
            record_submission(
                problem_id, problem["title_zh"], submission_id=str(uuid4()),
                diagnosis=fresh,
                hints_used=(list(range(1, st.session_state.get("hint_level", 1) + 1)) if fresh else []),
            )
            st.session_state["practice_notice"] = (
                "已记录一次本地刷题提交，绿墙和提交次数已更新。此操作不代表 LeetCode 通过。"
            )
            st.rerun()
        except (OSError, ValueError, TypeError):
            st.error("本地提交保存失败，请检查活动文件格式和写入权限。")

if accept_clicked:
    try:
        mark_accepted(problem_id, problem["title_zh"])
        st.session_state["practice_notice"] = (
            "已保存用户自报通过状态。完成题数已更新；此操作不额外增加提交次数。"
        )
        st.rerun()
    except (OSError, ValueError, TypeError):
        st.error("通过状态保存失败，请检查活动文件格式和写入权限。")
