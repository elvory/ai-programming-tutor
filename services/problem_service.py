"""Offline, extendable LeetCode practice catalog with original study summaries.

The catalog does not call private LeetCode APIs or copy official problem text.
Full and current statements remain available through each official link.

The catalog is validated once per file version and cached; callers always get
fresh copies so a search or page cannot alter later reads.
"""

import copy
import json
import os
from pathlib import Path
from threading import Lock


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "problem_catalog.json"
STAGE_TITLES = (
    "数组与哈希表", "双指针与滑动窗口", "栈、队列与二分查找", "链表",
    "二叉树与递归", "DFS、BFS 与回溯", "贪心算法", "动态规划",
)
DIFFICULTIES = ("Easy", "Medium", "Hard")
REQUIRED_FIELDS = (
    "id", "title_zh", "title_en", "slug", "difficulty", "tags", "stage",
    "summary", "examples", "constraints", "python_template", "official_url",
    "source_note",
)
TEXT_FIELDS = (
    "title_zh", "title_en", "slug", "summary", "python_template",
    "official_url", "source_note",
)
_CACHE = {"key": None, "problems": None}
_CACHE_LOCK = Lock()


class CatalogError(ValueError):
    """A catalog-loading problem safe to show to the user without a traceback."""


def _catalog_path():
    """Resolve at call time so tests and deployments can isolate the catalog."""
    return Path(os.environ.get("AI_TUTOR_CATALOG_PATH") or CATALOG_PATH).expanduser()


def _reject_constant(value):
    raise ValueError(f"题库包含非法 JSON 数值：{value}")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _validate_problem(problem, position):
    if not isinstance(problem, dict):
        raise CatalogError(f"题库第 {position} 项必须是 JSON 对象。")
    missing = [field for field in REQUIRED_FIELDS if field not in problem]
    if missing:
        raise CatalogError(f"题库第 {position} 项缺少必填字段：{'、'.join(missing)}。")
    problem_id = problem["id"]
    if type(problem_id) is not int or problem_id <= 0:
        raise CatalogError(f"题库第 {position} 项的 id 必须是正整数。")
    label = f"题目 #{problem_id}"

    for field in TEXT_FIELDS:
        if not _text(problem[field]):
            raise CatalogError(f"{label}的 {field} 必须是非空字符串。")
    if not problem["official_url"].strip().startswith(("http://", "https://")):
        raise CatalogError(f"{label}的 official_url 必须是以 http:// 或 https:// 开头的链接。")
    if problem["difficulty"] not in DIFFICULTIES:
        raise CatalogError(f"{label}的 difficulty 必须是 Easy、Medium 或 Hard。")
    if type(problem["stage"]) is not int or not 1 <= problem["stage"] <= 8:
        raise CatalogError(f"{label}的 stage 必须是 1 到 8 的整数。")

    tags = problem["tags"]
    if not isinstance(tags, list) or not tags or any(not _text(tag) for tag in tags):
        raise CatalogError(f"{label}的 tags 必须是由非空字符串组成的非空列表。")
    constraints = problem["constraints"]
    if not isinstance(constraints, list) or not constraints or any(not _text(item) for item in constraints):
        raise CatalogError(f"{label}的 constraints 必须是由非空字符串组成的非空列表。")
    examples = problem["examples"]
    if not isinstance(examples, list) or not examples:
        raise CatalogError(f"{label}的 examples 必须是至少包含一个示例的非空列表。")
    for number, example in enumerate(examples, 1):
        if (not isinstance(example, dict) or not _text(example.get("input"))
                or not _text(example.get("output"))):
            raise CatalogError(f"{label}的第 {number} 个示例必须包含非空的 input 和 output 字符串。")


def _validate_catalog(problems):
    if not isinstance(problems, list):
        raise CatalogError("题库 JSON 根节点必须是题目列表。")
    if not problems:
        raise CatalogError("题库不能为空。")
    seen = set()
    for position, problem in enumerate(problems, 1):
        _validate_problem(problem, position)
        if problem["id"] in seen:
            raise CatalogError(f"题库存在重复题号 #{problem['id']}。")
        seen.add(problem["id"])
    # Empty stages are allowed on purpose: pages must tolerate a missing stage
    # instead of failing while looking up the recommended problem.
    return problems


def _read_catalog_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise CatalogError("题库文件不存在，请检查 data/problem_catalog.json 是否存在。") from None
    except (OSError, UnicodeError):
        raise CatalogError("无法读取题库文件，请检查文件编码（UTF-8）与读取权限。") from None


def _catalog():
    """Return the validated cached list; never expose it to callers."""
    path = _catalog_path()
    try:
        stat = path.stat()
    except FileNotFoundError:
        raise CatalogError("题库文件不存在，请检查 data/problem_catalog.json 是否存在。") from None
    except OSError:
        raise CatalogError("无法读取题库文件，请检查文件权限。") from None
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    with _CACHE_LOCK:
        if _CACHE["key"] == key:
            return _CACHE["problems"]

    text = _read_catalog_text(path)
    try:
        problems = json.loads(text, parse_constant=_reject_constant)
    except json.JSONDecodeError as error:
        raise CatalogError(
            f"题库 JSON 解析失败：第 {error.lineno} 行第 {error.colno} 列格式错误。"
        ) from None
    except ValueError as error:
        raise CatalogError(str(error)) from None
    _validate_catalog(problems)
    with _CACHE_LOCK:
        _CACHE["key"] = key
        _CACHE["problems"] = problems
    return problems


def load_problems():
    """Return a fresh, validated catalog so callers cannot alter later searches."""
    return copy.deepcopy(_catalog())


def get_problem(problem_id):
    try:
        number = int(problem_id)
    except (ValueError, TypeError):
        return None
    for problem in _catalog():
        if problem["id"] == number:
            return copy.deepcopy(problem)
    return None


def search_problems(query="", difficulty=None, tags=None):
    query = str(query or "").strip().casefold()
    requested_tags = {tags} if isinstance(tags, str) else set(tags or [])
    return [
        copy.deepcopy(problem) for problem in _catalog()
        if (not query or (
            str(problem["id"]) == query if query.isdigit() else
            query in problem["title_zh"].casefold() or query in problem["title_en"].casefold()
        ))
        and (not difficulty or problem["difficulty"] == difficulty)
        and requested_tags.issubset(problem["tags"])
    ]


def get_learning_route():
    """Eight ordered stages; a stage may be empty if the catalog lacks it."""
    problems = load_problems()
    return [
        {"id": stage, "title": title,
         "problems": [problem for problem in problems if problem["stage"] == stage]}
        for stage, title in enumerate(STAGE_TITLES, start=1)
    ]
