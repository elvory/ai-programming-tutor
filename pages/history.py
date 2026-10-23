import streamlit as st

from services.activity_service import load_activities
from services.history_service import build_activity_rows, build_history_rows, display_value
from services.record_service import load_records
from utils.ui import configure_page


configure_page("学习记录 · AI Programming Tutor")
st.title("学习记录")
st.caption("AI 诊断、本地刷题提交和用户自报通过分别保存。完成状态来自用户确认，并非 LeetCode 官方同步。")

# Read both sources independently: one damaged file must not hide the other.
records, activities = None, None
record_error, activity_error = None, None
try:
    records = load_records()
except (OSError, ValueError):
    record_error = "无法读取学习记录，请检查记录文件格式和读取权限。"
try:
    activities = load_activities()
except (OSError, ValueError):
    activity_error = "无法读取刷题活动，请检查活动文件格式和读取权限。"

diagnosis_tab, activity_tab = st.tabs(["AI 诊断记录", "刷题活动"])
with diagnosis_tab:
    if record_error:
        st.error(record_error)
    elif not records:
        st.info("暂无学习记录，完成一次 AI 诊断后可在这里查看。")
    else:
        rows = build_history_rows(records, activities or [])
        if activity_error:
            st.warning("刷题活动暂时无法读取，因此本地完成状态暂不可用；诊断记录仍完整展示。")
            for row in rows:
                row["本地完成状态"] = "暂不可用（活动读取失败）"
        st.caption("旧记录缺失的题号、时间和 Hint 使用情况显示为“未记录”；旧版 Hint 等级不代表实际求助深度。")
        st.dataframe(rows, width="stretch", hide_index=True)

with activity_tab:
    if activity_error:
        st.error(activity_error)
    elif not activities:
        st.info("暂无刷题活动。请在练习页点击“记录本次刷题提交”；点击 AI 诊断不会自动增加提交次数。")
    else:
        st.caption("本地完成状态反映这道题当前的用户自报通过状态，和某次提交是否通过是不同的概念。")
        st.dataframe(build_activity_rows(activities), width="stretch", hide_index=True)
