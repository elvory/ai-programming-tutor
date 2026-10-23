"""Read-only presentation of new and legacy learning history."""

from services.record_service import validate_record


def display_value(record, field):
    """区分缺字段和空值，保留 0、False 等历史原值。"""
    if field not in record:
        return "未记录"
    value = record[field]
    if value is None:
        return "空值（null）"
    if isinstance(value, str):
        if value == "":
            return '空字符串（""）'
        if not value.strip():
            return f"空白字符串（{value!r}）"
    return str(value)


def _first_value(record, *fields):
    for field in fields:
        if field in record:
            return display_value(record, field)
    return "未记录"


def _problem_id(record):
    for field in ("leetcode_id", "problem_id"):
        value = record.get(field)
        if type(value) is int and value > 0:
            return value
        if isinstance(value, str) and value.isdecimal():
            try:
                parsed = int(value)
            except ValueError:
                continue
            if parsed > 0:
                return parsed
    return None


def _hint_usage(record):
    if "hints_used" not in record:
        return "未记录"
    hints = record["hints_used"]
    if not isinstance(hints, list) or any(type(level) is not int or level not in (1, 2, 3)
                                          for level in hints):
        return "记录异常：" + display_value(record, "hints_used")
    return "Hint " + "、".join(str(level) for level in sorted(set(hints))) if hints else "未使用"


def _accepted_ids(activities):
    from services.activity_service import summarize_activity

    return summarize_activity(activities, [])["completed_ids"]


def _completion(record, accepted):
    problem_id = _problem_id(record)
    if problem_id is None:
        return "未记录题号"
    return "用户自报已通过（非官方同步）" if problem_id in accepted else "未确认通过"


def build_history_rows(records, activities):
    """保留每条历史及原始索引，不修复、丢弃或修改源记录。"""
    fields = {
        "question": "题目", "error_type": "错误类型",
        "knowledge": "知识点", "hint_level": "Hint 等级",
    }
    rows = []
    accepted = _accepted_ids(activities)
    for index, record in enumerate(records):
        status, issue = "完整", ""
        try:
            validate_record(record)
        except ValueError as exc:
            status = "记录异常"
            issue = str(exc)
            if isinstance(record, dict) and any(field not in record for field in fields):
                status = "记录不完整"
            if not isinstance(record, dict):
                issue += f"；实际类型：{type(record).__name__}；原始值：{record!r}"
        row = {"原始索引": str(index), "状态": status, "异常说明": issue}
        row.update({
            label: display_value(record, field) if isinstance(record, dict) else "不适用"
            for field, label in fields.items()
        })
        if isinstance(record, dict):
            row.update({
                "LeetCode 题号": _first_value(record, "leetcode_id", "problem_id"),
                "题目名称": _first_value(record, "title", "problem_title"),
                "提交日期": _first_value(record, "created_at", "timestamp"),
                "Hint 使用情况": _hint_usage(record),
                "本地完成状态": _completion(record, accepted),
            })
        else:
            row.update({field: "不适用" for field in (
                "LeetCode 题号", "题目名称", "提交日期", "Hint 使用情况", "本地完成状态")})
        rows.append(row)
    return rows


def build_activity_rows(activities):
    """本地活动与AI诊断独立展示；所有异常项仍有对应表格行。"""
    from services.activity_service import validate_activity

    accepted = _accepted_ids(activities)
    rows = []
    for index, activity in enumerate(activities):
        row = {"原始索引": str(index), "状态": "完整", "异常说明": ""}
        try:
            validate_activity(activity)
        except (ValueError, TypeError, OverflowError) as exc:
            row["状态"] = "记录异常"
            row["异常说明"] = str(exc)
            if not isinstance(activity, dict):
                row["异常说明"] += f"；实际类型：{type(activity).__name__}；原始值：{activity!r}"
        if isinstance(activity, dict):
            kind = activity.get("kind")
            kind_label = ("本地刷题提交" if kind == "submission" else
                          "用户自报 LeetCode 通过" if kind == "accepted" else
                          display_value(activity, "kind"))
            row.update({
                "LeetCode 题号": _first_value(activity, "problem_id", "leetcode_id"),
                "题目名称": _first_value(activity, "title", "problem_title"),
                "活动类型": kind_label,
                "提交日期": _first_value(activity, "timestamp", "created_at"),
                "Hint 使用情况": _hint_usage(activity),
                "本地完成状态": _completion(activity, accepted),
            })
            diagnosis = activity.get("diagnosis")
            row["错误类型"] = display_value(diagnosis, "error_type") if isinstance(diagnosis, dict) else "未记录"
        else:
            row.update({field: "不适用" for field in (
                "LeetCode 题号", "题目名称", "活动类型", "提交日期", "Hint 使用情况", "本地完成状态", "错误类型")})
        rows.append(row)
    return rows
