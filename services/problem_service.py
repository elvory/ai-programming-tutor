"""Offline, extendable LeetCode practice catalog with original study summaries.

The catalog does not call private LeetCode APIs or copy official problem text.
Full and current statements remain available through each official link.
"""

import json
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "problem_catalog.json"
STAGE_TITLES = (
    "数组与哈希表", "双指针与滑动窗口", "栈、队列与二分查找", "链表",
    "二叉树与递归", "DFS、BFS 与回溯", "贪心算法", "动态规划",
)


def load_problems():
    """Return a fresh catalog so callers cannot alter later searches."""
    with CATALOG_PATH.open("r", encoding="utf-8") as catalog_file:
        return json.load(catalog_file)


def get_problem(problem_id):
    try:
        number = int(problem_id)
    except (ValueError, TypeError):
        return None
    return next((problem for problem in load_problems() if problem["id"] == number), None)


def search_problems(query="", difficulty=None, tags=None):
    query = str(query or "").strip().casefold()
    requested_tags = {tags} if isinstance(tags, str) else set(tags or [])
    return [
        problem for problem in load_problems()
        if (not query or (
            str(problem["id"]) == query if query.isdigit() else
            query in problem["title_zh"].casefold() or query in problem["title_en"].casefold()
        ))
        and (not difficulty or problem["difficulty"] == difficulty)
        and requested_tags.issubset(problem["tags"])
    ]


def get_learning_route():
    """Eight ordered stages with problems from the same catalog as search."""
    problems = load_problems()
    return [
        {"id": stage, "title": title,
         "problems": [problem for problem in problems if problem["stage"] == stage]}
        for stage, title in enumerate(STAGE_TITLES, start=1)
    ]
