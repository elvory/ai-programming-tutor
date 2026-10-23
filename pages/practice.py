"""Problem selection, session-scoped drafts, coaching, and explicit activities."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import streamlit as st

from services.activity_service import load_activities, mark_accepted, record_submission, summarize_activity
from services.llm_service import analyze_code, normalize_diagnosis
from services.practice_service import reveal_next_hint, save_draft, select_problem, set_diagnosis
from services.problem_service import get_problem, load_problems, search_problems
from services.record_service import save_record, update_record
from utils.ui import configure_page


def persist_editor(problem_id, editor_key):
    save_draft(st.session_state, problem_id, st.session_state[editor_key])


configure_page("代码练习 · AI Programming Tutor")
st.title("选一道题，开始思考。")
st.caption("离线精选题库 · 原创练习摘要与示例 · 完整题面及最终判题以 LeetCode 官方页面为准")

problems = load_problems()
requested = st.session_state.pop("requested_problem_id", None)
if requested is not None:
    st.session_state["problem_search"] = ""
    st.session_state["difficulty_filter"] = "全部"
    st.session_state["tag_filter"] = []
    st.session_state["problem_picker"] = requested

search, difficulty = st.columns([3, 1])
query = search.text_input("搜索题号或中英文题名", key="problem_search", placeholder="例如：1 / 两数之和 / Two Sum")
level = difficulty.selectbox("难度", ["全部", "Easy", "Medium", "Hard"], key="difficulty_filter")
tags = st.multiselect("算法标签", sorted({tag for p in problems for tag in p["tags"]}), key="tag_filter")
matches = search_problems(query=query, difficulty=None if level == "全部" else level, tags=tags)
st.caption(f"找到 {len(matches)} 道题 · 支持题号、中文名和英文名搜索")
if not matches:
    st.info("没有匹配题目，请调整搜索或筛选条件。已有草稿仍保留在当前会话中。")
    st.stop()

ids = [p["id"] for p in matches]
if st.session_state.get("problem_picker") not in ids:
    preferred = st.session_state.get("selected_problem_id")
    st.session_state["problem_picker"] = preferred if preferred in ids else ids[0]
problem_id = st.selectbox(
    "选择题目", ids, key="problem_picker",
    format_func=lambda pid: f"#{pid} · {get_problem(pid)['title_zh']} / {get_problem(pid)['title_en']}",
)
problem = get_problem(problem_id)
draft = select_problem(st.session_state, problem)
notice = st.session_state.pop("practice_notice", None)
if notice:
    st.success(notice)

st.subheader(f"#{problem_id} · {problem['title_zh']}")
st.caption(f"{problem['title_en']} · {problem['difficulty']} · {' / '.join(problem['tags'])}")
st.link_button("在 LeetCode 查看完整题目 ↗", problem["official_url"])
with st.expander("题目说明、示例与约束", expanded=True):
    st.markdown(problem["summary"])
    for number, example in enumerate(problem["examples"], 1):
        st.markdown(f"**练习示例 {number}**")
        st.code(f"输入：{example['input']}\n输出：{example['output']}", language="text")
        if example.get("explanation"):
            st.caption(example["explanation"])
    st.markdown("**练习约束**")
    for constraint in problem["constraints"]:
        st.markdown(f"- {constraint}")
    st.caption(problem["source_note"])

st.subheader("Python 编辑区", divider="green")
editor_key = f"code_editor_{problem_id}"
if editor_key not in st.session_state:
    st.session_state[editor_key] = draft
code = st.text_area("Python 3 代码", key=editor_key, height=340, on_change=persist_editor, args=(problem_id, editor_key))
save_draft(st.session_state, problem_id, code)
st.caption("每题独立草稿，当前浏览器会话内保留；切换页面、查看 Hint 和重新诊断均不会覆盖代码。关闭或刷新会话前请自行备份。")

diagnosis = st.session_state.get("diagnosis")
has_diagnosis = diagnosis is not None and st.session_state.get("diagnosis_problem_id") == problem_id
if st.button("重新诊断" if has_diagnosis else "AI 诊断（Mock）", type="primary", key="diagnose"):
    if not code.strip():
        st.warning("请先填写代码，再开始诊断。")
    else:
        try:
            with st.spinner("正在检查当前题目与代码…"):
                result = normalize_diagnosis(analyze_code(code, problem))
        except Exception:
            result = None
            st.error("诊断失败，请稍后重试。草稿已保留。")
        if result is None:
            st.error("未获得有效的诊断结果，草稿已保留。")
        else:
            record_id = str(uuid4())
            record = {
                "question": f"#{problem_id} {problem['title_zh']}：{problem['summary']}",
                "error_type": result["error_type"], "knowledge": result["knowledge"], "hint_level": 1,
                "record_id": record_id, "leetcode_id": problem_id, "title": problem["title_zh"],
                "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "hints_used": [1], "is_mock": True,
            }
            try:
                save_record(record)
            except (OSError, ValueError, TypeError):
                record_id = None
                st.warning("诊断已完成，但诊断记录保存失败。请检查记录文件格式和写入权限。")
            set_diagnosis(st.session_state, problem_id, code, result, record_id)

diagnosis = st.session_state.get("diagnosis")
current_diagnosis = diagnosis if st.session_state.get("diagnosis_problem_id") == problem_id else None
if current_diagnosis:
    st.subheader("AI 辅导 · Mock 模拟诊断", divider="green")
    st.caption("当前使用本地规则与语法检查，未接入真实大模型，也不会运行你的代码。诊断结果不代表 LeetCode 判题结果。")
    if code != st.session_state.get("diagnosed_code"):
        st.warning("代码已修改，下面是上一版代码的分析。请点击「重新诊断」更新结果。")
    st.markdown(f"**错误类型：** {current_diagnosis['error_type']}")
    st.markdown(f"**知识点：** {current_diagnosis['knowledge']}")
    st.write(current_diagnosis["analysis"])
    shown = st.session_state.get("hint_level", 1)
    for index, hint in enumerate(current_diagnosis["hints"][:shown], 1):
        st.info(f"Hint {index} · {hint}")
    if st.button("查看下一条 Hint", key="next_hint", disabled=shown >= len(current_diagnosis["hints"])):
        shown = reveal_next_hint(st.session_state)
        record_id = st.session_state.get("diagnosis_record_id")
        if record_id:
            try:
                updated = update_record(record_id, {"hint_level": shown, "hints_used": list(range(1, shown + 1))})
                if not updated:
                    st.session_state["hint_save_warning"] = True
            except (OSError, ValueError, TypeError):
                st.session_state["hint_save_warning"] = True
        st.rerun()
    if st.session_state.pop("hint_save_warning", False):
        st.warning("Hint 已展示，但本次使用情况未能保存。")

st.subheader("记录本次学习", divider="green")
st.caption("AI 诊断、一次本地提交、LeetCode 已通过是三种独立操作。绿墙只统计你主动记录的本地提交。")
try:
    activities = load_activities()
    completed = summarize_activity(activities, problems)["completed_ids"]
    accepted = problem_id in completed
    st.caption("本地完成状态：" + ("已在 LeetCode 通过（用户自报）" if accepted else "尚未确认通过"))
except (OSError, ValueError):
    accepted = False
    st.error("无法读取本地活动。请检查活动文件，保存操作不会覆盖损坏数据。")

if st.button("记录一次本地提交", key="record_submission"):
    if not code.strip():
        st.warning("请先填写代码，再记录本地提交。")
    else:
        fresh = current_diagnosis if code == st.session_state.get("diagnosed_code") else None
        try:
            record_submission(problem_id, problem["title_zh"], submission_id=str(uuid4()),
                              diagnosis=fresh, hints_used=list(range(1, st.session_state.get("hint_level", 1) + 1)) if fresh else [])
            st.session_state["practice_notice"] = "已记录一次本地刷题提交，绿墙和提交次数已更新。此操作不代表 LeetCode 通过。"
            st.rerun()
        except (OSError, ValueError, TypeError):
            st.error("本地提交保存失败，请检查活动文件格式和写入权限。")

confirmed = st.checkbox("我确认这道题已在 LeetCode 提交并通过（用户自报）", key=f"confirm_accepted_{problem_id}")
if st.button("记录 LeetCode 已通过", key="record_accepted", disabled=not confirmed or accepted):
    try:
        mark_accepted(problem_id, problem["title_zh"])
        st.session_state["practice_notice"] = "已保存用户自报通过状态。完成题数已更新；此操作不额外增加提交次数。"
        st.rerun()
    except (OSError, ValueError, TypeError):
        st.error("通过状态保存失败，请检查活动文件格式和写入权限。")
