"""Server-side DeepSeek diagnosis; explicit offline rules remain available.

Student source is sent as UTF-8 data, never executed. Transport errors are
sanitized here so neither credentials nor upstream error bodies reach the UI.
"""

import ast
import json
import os
from pathlib import Path
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
RESPONSES_URL = "https://api.deepseek.com/responses"
DEFAULT_MODEL = "deepseek-flash"
RESPONSES_MODELS = ("deepseek-flash", "deepseek-v4-pro")
REQUEST_TIMEOUT = 30
SCHEMA_NAME = "code_diagnosis"
# Arrays cannot be length-constrained by every strict schema implementation;
# _strict_diagnosis still requires exactly three non-empty hints.
DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "error_type": {"type": "string"},
        "knowledge": {"type": "string"},
        "analysis": {"type": "string"},
        "hints": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["error_type", "knowledge", "analysis", "hints"],
    "additionalProperties": False,
}


class DiagnosisError(Exception):
    """A safe, actionable message; never include request/response secrets."""


def _strict_diagnosis(result):
    if not isinstance(result, dict):
        return None
    fields = ("error_type", "knowledge", "analysis")
    if any(not isinstance(result.get(field), str) or not result[field].strip() for field in fields):
        return None
    hints = result.get("hints")
    if (not isinstance(hints, list) or len(hints) != 3
            or any(not isinstance(hint, str) or not hint.strip() for hint in hints)):
        return None
    return {**{field: result[field].strip() for field in fields},
            "hints": [hint.strip() for hint in hints]}


def normalize_diagnosis(result):
    """为部分缺失的诊断补齐展示字段，拒绝空结果和错误响应。"""
    if not isinstance(result, dict):
        return None

    # AI results must never be repaired into an apparently successful diagnosis.
    if result.get("source") == "deepseek" or result.get("is_mock") is False:
        diagnosis = _strict_diagnosis(result)
        if diagnosis is None:
            return None
        diagnosis.update({"is_mock": False, "source": result.get("source", "unknown")})
        if isinstance(result.get("model"), str):
            diagnosis["model"] = result["model"]
        return diagnosis

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
    diagnosis["source"] = "rules"
    return diagnosis


def _with_context(result, problem):
    """Display explicit limits and use the selected catalog problem as context."""
    result["is_mock"] = True
    result["source"] = "rules"
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

def _response_text(body):
    """Extract output_text from Responses API message items without other data."""
    output = body.get("output") if isinstance(body, dict) else None
    if not isinstance(output, list):
        return ""
    parts = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if (isinstance(part, dict) and part.get("type") == "output_text"
                    and isinstance(part.get("text"), str)):
                parts.append(part["text"])
    return "".join(parts)


def analyze_code_rules(code, problem=None):
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


def analyze_code(code, problem=None):
    """Diagnose with DeepSeek; retain the optional problem/single-argument API.

    No retries or implicit rules fallback: a failed request raises DiagnosisError
    and must not create a successful diagnosis record.
    """
    if not isinstance(code, str):
        raise TypeError("代码必须为字符串。")
    if not code.strip():
        raise DiagnosisError("请先填写代码，再开始诊断。")
    try:
        load_dotenv(ROOT / ".env", override=False, encoding="utf-8")
    except (OSError, UnicodeError):
        raise DiagnosisError("无法加载服务端 .env，请检查文件权限与 UTF-8 编码。") from None
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise DiagnosisError("未配置 DEEPSEEK_API_KEY，请在服务端 .env 中设置后重启应用。")
    model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if model not in RESPONSES_MODELS:
        raise DiagnosisError("当前 Responses 结构化输出仅支持 deepseek-flash 或 deepseek-v4-pro，请调整 DEEPSEEK_MODEL。")
    try:
        prompt = (ROOT / "prompts" / "diagnose_prompt.txt").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise DiagnosisError("诊断 Prompt 无法读取，请检查 prompts/diagnose_prompt.txt。") from None
    context_fields = ("id", "title_zh", "title_en", "difficulty", "tags", "summary", "examples", "constraints")
    context = {field: problem[field] for field in context_fields if field in problem} if isinstance(problem, dict) else {}
    payload = {
        "model": model,
        "instructions": prompt,
        "input": json.dumps({"problem": context, "code": code}, ensure_ascii=False),
        "reasoning": {"effort": "none"},
        "max_output_tokens": 1800,
        "stream": False,
        "text": {"format": {"type": "json_schema", "name": SCHEMA_NAME, "schema": DIAGNOSIS_SCHEMA}},
    }
    try:
        request = Request(RESPONSES_URL, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json; charset=utf-8"},
                          method="POST")
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read()
    except HTTPError as error:
        status = error.code
        error.close()
        messages = {
            401: "认证失败，请检查服务端密钥是否有效。",
            402: "账户余额不足，请检查 DeepSeek 账户余额。",
            429: "请求过于频繁，请稍后手动重试。",
            400: "请求格式或模型不可用，请核对 DEEPSEEK_MODEL 与官方参数说明。",
            422: "请求参数不受支持，请核对模型与官方参数说明。",
        }
        raise DiagnosisError(f"DeepSeek 请求失败（HTTP {status}）：" + messages.get(status, "服务暂不可用，请稍后手动重试。")) from None
    except (TimeoutError, socket.timeout):
        raise DiagnosisError("DeepSeek 请求超时，请稍后手动重试。") from None
    except URLError as error:
        timed_out = isinstance(error.reason, (TimeoutError, socket.timeout))
        raise DiagnosisError("DeepSeek 请求超时，请稍后手动重试。" if timed_out else "无法连接 DeepSeek，请检查网络后手动重试。") from None
    except (OSError, ValueError):
        raise DiagnosisError("DeepSeek 请求未能完成，请检查服务端配置与网络。") from None
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        raise DiagnosisError("DeepSeek 响应不是有效 JSON，未生成诊断，请手动重试。") from None
    if (not isinstance(body, dict) or "status" not in body
            or not isinstance(body.get("output"), list)):
        raise DiagnosisError("DeepSeek 响应缺少必要字段，未生成诊断。")
    if body["status"] != "completed":
        raise DiagnosisError("DeepSeek 响应未完整结束，未生成诊断，请手动重试。")
    content = _response_text(body)
    if not isinstance(content, str) or not content.strip():
        raise DiagnosisError("DeepSeek 返回空响应，未生成诊断，请手动重试。")
    try:
        result = _strict_diagnosis(json.loads(content))
    except ValueError:
        raise DiagnosisError("DeepSeek 诊断不是有效 JSON，未生成诊断，请手动重试。") from None
    if result is None:
        raise DiagnosisError("DeepSeek 诊断缺字段或格式错误，必须包含错误类型、知识点、分析和恰好三级非空 Hint。")
    # Provenance is assigned by the service, never trusted from model content.
    result.update({"source": "deepseek", "is_mock": False, "model": model})
    return result
