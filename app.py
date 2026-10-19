import streamlit as st
from services.llm_service import analyze_code
from services.record_service import save_record

st.title("AI Programming Tutor")

st.write("基于大语言模型的渐进式编程学习与知识诊断系统")


#初始化状态
if "diagnosis" not in st.session_state:
    st.session_state.diagnosis = None

if "hint_level" not in st.session_state:
    st.session_state.hint_level = 1


# 清除旧的诊断结果
def clear_diagnosis():
    st.session_state.diagnosis = None
    st.session_state.hint_level = 1


def normalize_diagnosis(result):
    """为部分缺失的诊断补齐展示字段，拒绝空结果和错误响应。"""
    if not isinstance(result, dict):
        return None

    hints = result.get("hints")
    hints = [hint.strip() for hint in hints
             if isinstance(hint, str) and hint.strip()] if isinstance(hints, list) else []
    fields = ("error_type", "knowledge", "analysis")
    if not hints and not any(
        isinstance(result.get(field), str) and result[field].strip()
        for field in fields
    ):
        return None

    defaults = {
        "error_type": "未知",
        "knowledge": "未知",
        "analysis": "暂未提供问题分析。",
    }
    diagnosis = {
        field: result[field].strip()
        if isinstance(result.get(field), str) and result[field].strip() else default
        for field, default in defaults.items()
    }
    diagnosis["hints"] = hints or ["暂未提供提示，请结合问题分析检查代码。"]
    return diagnosis


#用户输入
question = st.text_area(
     "请输入编程题目",
     key = "question_input",
     on_change = clear_diagnosis
)
code = st.text_area(
     "请输入你的代码",
     height=200,
     key = "code_input",
     on_change = clear_diagnosis
)

#开始诊断
if st.button("开始AI诊断"):
    if not question.strip() or not code.strip():
        st.session_state.diagnosis = None
        st.warning("请先输入题目和代码！")

    else:
        clear_diagnosis()
        try:
            result = normalize_diagnosis(analyze_code(code))
        except Exception:
            st.error("诊断失败，请稍后重试。")
        else:
            if result is None:
                st.error("未获得有效的诊断结果，请重试。")
            else:
                st.session_state.diagnosis = result
                # 保存仅在本次按钮操作成功诊断后执行；Hint 和普通重运行不会保存。
                record = {
                    "question": question,
                    "error_type": result["error_type"],
                    "knowledge": result["knowledge"],
                    "hint_level": 1,
                }
                try:
                    save_record(record)
                except (OSError, ValueError, TypeError):
                    st.warning("诊断已完成，但学习记录保存失败，请检查记录文件格式和写入权限。")

#显示诊断结果
if st.session_state.diagnosis is not None:
        result = st.session_state.diagnosis

        st.subheader("AI 诊断结果")

        st.write("**错误类型：**",result["error_type"])
        st.write("**涉及知识点：**",result["knowledge"])
        st.write("**问题分析：**",result["analysis"])

        #获取当前提示等级
        level = st.session_state.hint_level

        st.info(f"💡 Hint {level}：" + result["hints"][level-1])

        #判断是否还有下一级提示
        if level < len(result["hints"]):

             if st.button("我还是不会，给我下一个Hint"):
                  st.session_state.hint_level +=1
                  st.rerun()

        else:
             st.success("已经显示全部提示，请尝试独立完成代码！")
