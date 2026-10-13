import re

import streamlit as st
from services.llm_service import analyze_code

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
        result = analyze_code(code)

        #保存诊断结果
        st.session_state.diagnosis = result

        #每次重新诊断，从Hint 1 开始
        st.session_state.hint_level = 1

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
