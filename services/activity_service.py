"""Submission and self-reported acceptance events, independent of diagnoses.

JSON writes are atomic and serialized within one Python process. Separate
processes need external coordination; replacement alone cannot prevent a lost
read/modify/write update across processes.
"""

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from threading import Lock
from time import sleep
from uuid import uuid4


FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "activities.json"
SHANGHAI = timezone(timedelta(hours=8), "Asia/Shanghai")
_SAVE_LOCK = Lock()


def _activity_path():
    return Path(os.environ.get("AI_TUTOR_ACTIVITIES_PATH") or FILE_PATH).expanduser()


def _reject_constant(value):
    raise ValueError(f"活动文件包含非法 JSON 数值：{value}")


def load_activities():
    """Preserve legacy list entries; malformed JSON or a non-list root raises."""
    try:
        with _activity_path().open("r", encoding="utf-8") as file:
            activities = json.load(file, parse_constant=_reject_constant)
    except FileNotFoundError:
        return []
    if not isinstance(activities, list):
        raise ValueError("活动文件的 JSON 根节点必须是列表。")
    return activities


def _timestamp(value):
    if value is None:
        return datetime.now(SHANGHAI)
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else ""))
        except ValueError as exc:
            raise ValueError("timestamp 必须是带时区的 ISO 时间。") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp 必须是带时区的 ISO 时间。")
    return value.astimezone(SHANGHAI)


def _positive_id(value):
    return type(value) is int and value > 0


def validate_activity(activity):
    """Validate one event without modifying it; optional snapshots must be JSON-safe."""
    if not isinstance(activity, dict):
        raise ValueError("活动必须是字典。")
    kind = activity.get("kind")
    if kind not in ("submission", "accepted"):
        raise ValueError("kind 必须是 submission 或 accepted。")
    if not _positive_id(activity.get("problem_id")):
        raise ValueError("problem_id 必须是正整数。")
    if not isinstance(activity.get("title"), str) or not activity["title"].strip():
        raise ValueError("title 必须是非空字符串。")
    if not isinstance(activity.get("timestamp"), str):
        raise ValueError("timestamp 必须是带时区的 ISO 时间。")
    _timestamp(activity["timestamp"])
    identity = "submission_id" if kind == "submission" else "event_id"
    if not isinstance(activity.get(identity), str) or not activity[identity].strip():
        raise ValueError(f"{identity} 必须是非空字符串。")
    if "diagnosis" in activity and activity["diagnosis"] is not None and not isinstance(activity["diagnosis"], dict):
        raise ValueError("diagnosis 快照必须是字典。")
    if "hints_used" in activity:
        hints = activity["hints_used"]
        if not isinstance(hints, list) or any(not _positive_id(hint) for hint in hints):
            raise ValueError("hints_used 必须是正整数列表。")
        if len(hints) != len(set(hints)):
            raise ValueError("hints_used 不能重复。")
    try:
        json.dumps(activity, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("活动快照必须是可序列化的 JSON，且不包含 NaN 或 Infinity。") from exc


def _write_activities(activities):
    content = json.dumps(activities, ensure_ascii=False, indent=2, allow_nan=False)
    path = _activity_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".activities-", suffix=".tmp", delete=False) as file:
            temporary_path = Path(file.name)
            file.write(content)
        # Readers/scanners may briefly hold Windows handles without delete sharing.
        for attempt in range(5):
            try:
                os.replace(temporary_path, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                sleep(0.01 * 2 ** attempt)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _append_event(event):
    validate_activity(event)
    identity = "submission_id" if event["kind"] == "submission" else "event_id"
    with _SAVE_LOCK:
        activities = load_activities()
        for old in activities:
            if isinstance(old, dict) and old.get("kind") == event["kind"] and old.get(identity) == event[identity]:
                validate_activity(old)
                if old["problem_id"] != event["problem_id"]:
                    raise ValueError("同一活动 ID 不能用于不同题目。")
                return old
        activities.append(event)
        _write_activities(activities)
    return event


def record_submission(problem_id, title, *, submission_id=None, timestamp=None,
                      diagnosis=None, hints_used=None):
    event = {"kind": "submission", "problem_id": problem_id, "title": title,
             "timestamp": _timestamp(timestamp).isoformat(),
             "submission_id": uuid4().hex if submission_id is None else submission_id}
    if diagnosis is not None:
        event["diagnosis"] = diagnosis
    if hints_used is not None:
        event["hints_used"] = hints_used
    return _append_event(event)


def mark_accepted(problem_id, title, *, event_id=None, timestamp=None):
    """Record a user-reported LeetCode acceptance; this is not a submission."""
    return _append_event({"kind": "accepted", "problem_id": problem_id, "title": title,
                          "timestamp": _timestamp(timestamp).isoformat(),
                          "event_id": uuid4().hex if event_id is None else event_id})


def _today(value):
    if value is None:
        return datetime.now(SHANGHAI).date()
    if isinstance(value, datetime):
        return _timestamp(value).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("today 必须是日期或带时区时间。")


def _valid_events(activities, today):
    """Ignore malformed/future events and repeated event identities in views only."""
    seen = set()
    for activity in activities:
        try:
            validate_activity(activity)
            event_date = _timestamp(activity["timestamp"]).date()
        except (ValueError, OverflowError):
            continue
        if event_date > today:
            continue
        identity = (activity["kind"], activity.get("submission_id") if activity["kind"] == "submission"
                    else activity.get("event_id"))
        if identity in seen:
            continue
        seen.add(identity)
        yield activity, event_date


def summarize_activity(activities, problems, today=None):
    """Summarize submissions, user-reported completions, and submission-day streaks."""
    today = _today(today)
    counts = {}
    completed = set()
    for activity, event_date in _valid_events(activities, today):
        if activity["kind"] == "submission":
            day = event_date.isoformat()
            counts[day] = counts.get(day, 0) + 1
        else:
            completed.add(activity["problem_id"])
    current = today if today.isoformat() in counts else today - timedelta(days=1)
    streak = 0
    while current.isoformat() in counts:
        streak += 1
        current -= timedelta(days=1)
    stages = {}
    for problem in problems:
        if not isinstance(problem, dict):
            continue
        problem_id, stage = problem.get("id"), problem.get("stage")
        if _positive_id(problem_id) and type(stage) is int and 1 <= stage <= 8:
            stages.setdefault(stage, set()).add(problem_id)
    recommended = 1
    if counts or completed:
        recommended = next((stage for stage in sorted(stages)
                            if not stages[stage].issubset(completed)), 8 if stages else 1)
    return {"total_submissions": sum(counts.values()), "completed_problems": len(completed),
            "streak_days": streak, "recommended_stage": recommended,
            "completed_ids": completed, "counts_by_day": dict(sorted(counts.items()))}


def build_heatmap(activities, today=None, days=365):
    """Return an inclusive date window; levels are 0, 1, 2, 3, and 4+ submissions."""
    if type(days) is not int or days <= 0:
        raise ValueError("days 必须是正整数。")
    today = _today(today)
    counts = summarize_activity(activities, [], today)["counts_by_day"]
    first = today - timedelta(days=days - 1)
    result = []
    for offset in range(days):
        day = (first + timedelta(days=offset)).isoformat()
        count = counts.get(day, 0)
        result.append({"date": day, "count": count, "level": min(count, 4)})
    return result


def problem_status(activities, problem_id, today=None):
    """Status from valid past/present events, independent of diagnosis records."""
    if not _positive_id(problem_id):
        raise ValueError("problem_id 必须是正整数。")
    count, accepted, latest = 0, False, None
    for activity, _ in _valid_events(activities, _today(today)):
        if activity["problem_id"] != problem_id:
            continue
        if activity["kind"] == "accepted":
            accepted = True
        else:
            count += 1
            timestamp = _timestamp(activity["timestamp"])
            if latest is None or timestamp > latest:
                latest = timestamp
    return {"problem_id": problem_id, "accepted": accepted, "submission_count": count,
            "last_submission_at": latest.isoformat() if latest is not None else None}
