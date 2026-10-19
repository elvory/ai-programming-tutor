import streamlit as st

from services.record_service import load_records


st.title("学习记录")

try:
    records = load_records()
except (OSError, ValueError):
    st.error("无法读取学习记录，请检查记录文件格式和读取权限。")
else:
    if not records:
        st.info("暂无学习记录，完成一次诊断后可在这里查看。")
    else:
        rows = [
            {
                "题目": record.get("question", "未知"),
                "错误类型": record.get("error_type", "未知"),
                "知识点": record.get("knowledge", "未知"),
                "Hint 等级": str(record.get("hint_level") or "未知"),
            }
            for record in records if isinstance(record, dict)
        ]
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.warning("学习记录中暂无可展示的记录对象，请检查文件内容。")
