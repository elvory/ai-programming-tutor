"""Six-dimensional catalog completion coverage, not an inferred skill score.

One catalog stage determines a problem's primary dimension. Accepted IDs are
validated by the existing activity service and deduplicated across languages.
Nothing in this module reads or writes learning files or calls an AI model.
"""
from services.activity_service import summarize_activity


DIMENSIONS = (
    ("arrays-hash", "数组与哈希表", (1,)),
    ("pointers-window", "双指针与滑动窗口", (2,)),
    ("stack-search", "栈、队列与二分查找", (3,)),
    ("lists-trees", "链表、二叉树与递归", (4, 5)),
    ("search-backtrack", "DFS、BFS 与回溯", (6,)),
    ("greedy-dp", "贪心与动态规划", (7, 8)),
)
MIN_SAMPLE = 3


def _sample_status(completed):
    return "empty" if completed == 0 else "insufficient" if completed < MIN_SAMPLE else "available"


def build_capability_profile(activities, problems, today=None):
    """Return 0–100 completion percentages from valid self-reported passes.

The sample warning uses three distinct passed problems as a transparent V1
display threshold, not a statistical confidence or an interview prediction.
Unknown stages are reported separately and never guessed from ambiguous tags.
"""
    accepted = summarize_activity(activities, problems, today)["completed_ids"]
    stage_dimension = {stage: index for index, (_, _, stages) in enumerate(DIMENSIONS)
                       for stage in stages}
    members = [[] for _ in DIMENSIONS]
    seen, unclassified = set(), []
    for problem in problems:
        if not isinstance(problem, dict):
            continue
        pid, stage = problem.get("id"), problem.get("stage")
        if type(pid) is not int or pid <= 0 or pid in seen:
            continue
        seen.add(pid)
        if type(stage) is not int or stage not in stage_dimension:
            unclassified.append(pid)
            continue
        members[stage_dimension[stage]].append(pid)
    dimensions = []
    for (identity, label, stages), ids in zip(DIMENSIONS, members):
        completed_ids = sorted(set(ids) & accepted)
        remaining = [pid for pid in ids if pid not in accepted]
        dimensions.append({
            "id": identity, "label": label, "stages": list(stages), "problem_ids": ids,
            "total": len(ids), "completed_ids": completed_ids, "completed": len(completed_ids),
            "percentage": round(len(completed_ids) / len(ids) * 100, 1) if ids else 0,
            "sample_status": _sample_status(len(completed_ids)),
            "recommended_problem_id": remaining[0] if remaining else None,
        })
    completed = sum(row["completed"] for row in dimensions)
    comparable = [row for row in dimensions if row["total"]]
    pending = [row for row in comparable if row["completed"] < row["total"]]
    next_dimension = min(pending, key=lambda row: row["percentage"], default=None)
    strongest, needs_attention = [], []
    if completed >= MIN_SAMPLE and comparable:
        high = max(row["percentage"] for row in comparable)
        low = min(row["percentage"] for row in comparable)
        strongest = [row["label"] for row in comparable if row["percentage"] == high]
        needs_attention = [row["label"] for row in pending if row["percentage"] == low]
    note = ("暂无已确认通过的样本；0% 表示尚未记录完成，不代表真实能力为零。" if not completed else
            "样本不足：仅记录了少于 3 道不同题目的通过情况，暂不比较强弱方向。" if completed < MIN_SAMPLE else
            "以上仅比较题库完成度，不代表准确率、真实能力或面试水平。")
    if next_dimension:
        note += f" 建议继续练习「{next_dimension['label']}」，先独立思考，再按需使用 Hint。"
    elif comparable:
        note += " 当前题库已全部标记完成，可复盘边界条件或用其他语言巩固。"
    else:
        note += " 当前没有可分类的题目，请检查题库阶段。"
    return {
        "dimensions": dimensions, "completed_unique": completed,
        "total": sum(row["total"] for row in dimensions),
        "sample_status": _sample_status(completed), "strongest": strongest,
        "needs_attention": needs_attention, "recommendation": note,
        "recommended_problem_id": next_dimension["recommended_problem_id"] if next_dimension else None,
        "unclassified_problem_ids": sorted(unclassified),
    }
