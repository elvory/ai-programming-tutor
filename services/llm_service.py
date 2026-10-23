# AI 诊断逻辑模块：规则模拟版本，没有接入在线大模型，不执行学生代码。

import ast


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
    diagnosis["is_mock"] = result.get("is_mock") is not False
    return diagnosis


def _with_context(result, problem):
    """Display explicit limits and use the selected catalog problem as context."""
    result["is_mock"] = True
    context = ""
    if isinstance(problem, dict):
        title = problem.get("title_zh") or problem.get("title_en") or "当前题目"
        tags = "、".join(tag for tag in problem.get("tags", []) if isinstance(tag, str))
        context = f"当前题目：{title}。练习目标：{problem.get('summary', '')}"
        if tags:
            context += f"相关算法：{tags}。"
        result["hints"][0] = f"结合《{title}》的输入输出要求：" + result["hints"][0]
    result["analysis"] = (
        context + result["analysis"]
        + " 本结果为 Mock 规则模拟，仅进行静态检查，未执行代码；不代表 LeetCode 已通过。"
    )
    return result

def analyze_code(code, problem=None):
    """Statically inspect source with optional catalog context; never execute it.

    This keeps the original single-argument API and boundary heuristic. The
    optional problem supplies a title, study summary and tags, not an oracle.
    """
    if not isinstance(code, str):
        raise TypeError("代码必须为字符串。")
    if not code.strip():
        return _with_context({
            "error_type": "未提供代码", "knowledge": "Python 基础",
            "analysis": "请先在编辑区编写代码，再请求诊断。",
            "hints": ["先确认函数签名与题目一致。", "用自己的话描述输入与输出。", "尝试写出最简单的边界情况。"],
        }, problem)
    try:
        ast.parse(code)
    except SyntaxError as error:
        return _with_context({
            "error_type": "Python 语法错误", "knowledge": "Python 语法",
            "analysis": f"第 {error.lineno or 1} 行存在语法问题：{error.msg}。",
            "hints": [
                "先检查报错行与上一行的括号、冒号和引号。",
                "检查缩进是否一致，函数和条件块是否具有合法语句。",
                "修正语法后重新诊断；语法通过仍需自行验证题目逻辑。",
            ],
        }, problem)
    #删除空格，方便进行简单的规则匹配
    normalized_code = code.replace(" ","")

    if (
        "nums[i+1]" in normalized_code and "range(len(nums))" in normalized_code
    ):
        return _with_context({
            "is_mock": True,
            "error_type":"可能存在边界条件错误",
            "knowledge" :"列表索引",
            "analysis":"循环访问整个列表时，nums[i+1] 可能超出索引范围。",
            "hints":[
                    "思考一下，当i是最后一个元素的索引时，i+1是否仍然有效？",
                    "假设列表有4个元素，合法索引是0、1、2、3。当i=3时，i+1是多少？",
                    "尝试调整range()的循环范围，确保i+1始终小于len(nums)。"
            ]
        }, problem)

    # 没有匹配到当前演示规则
    return _with_context({
        "is_mock": True,
        "error_type": "未匹配到已知问题",
        "knowledge": "待进一步分析",
        "analysis": "当前模拟诊断模块尚未发现其支持识别的问题，但不代表代码一定正确。",
        "hints":[
            "先检查代码是否符合题目要求。",
            "尝试使用简单输入和边界情况进行测试。",
            "重点检查循环条件、变量变化和返回结果。"
        ]
    }, problem)
