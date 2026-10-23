import json
import os
from pathlib import Path
import tempfile
from threading import Lock
from time import sleep

FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "records.json"
_SAVE_LOCK = Lock()


def _record_path():
    """Resolve at call time so deployments and tests can isolate their data."""
    return Path(os.environ.get("AI_TUTOR_RECORDS_PATH") or FILE_PATH).expanduser()


def load_records():
    """读取历史；损坏的数据应报错，避免保存时覆盖原有记录。"""
    path = _record_path()
    try:
        with path.open("r", encoding="utf-8") as file:
            records = json.load(file)
    except FileNotFoundError:
        return []

    if not isinstance(records, list):
        raise ValueError("学习记录文件的 JSON 根节点必须是列表。")
    return records


def validate_record(record):
    """只校验本次新增的记录，不修改或校验已有历史列表。"""
    if not isinstance(record, dict):
        raise ValueError(f"新增学习记录必须是字典，实际类型为 {type(record).__name__}。")

    text_fields = ("question", "error_type", "knowledge")
    missing = [field for field in (*text_fields, "hint_level") if field not in record]
    errors = ["缺少必填字段：" + "、".join(missing)] if missing else []
    for field in text_fields:
        if field not in record:
            continue
        value = record[field]
        if value is None:
            errors.append(f"{field} 为空值（null）")
        elif not isinstance(value, str):
            errors.append(f"{field} 必须是字符串，实际类型为 {type(value).__name__}")
        elif not value.strip():
            errors.append(f"{field} 不能为空字符串或纯空白")

    if "hint_level" in record:
        level = record["hint_level"]
        if level is None:
            errors.append("hint_level 为空值（null），必须是正整数")
        elif type(level) is not int or level <= 0:
            errors.append(f"hint_level 必须是正整数，实际类型为 {type(level).__name__}，值为 {level!r}")
    if errors:
        raise ValueError("；".join(errors))


def save_record(record):
    validate_record(record)
    # Streamlit 同一进程的会话可能并发保存，锁住完整的读取和写入操作。
    with _SAVE_LOCK:
        _save_record(record)


def _save_record(record):
    records = load_records()
    records.append(record)
    _write_records(records)


def update_record(record_id, updates):
    """Update one identified record, preserving unrelated and legacy entries.

    Return False when the ID is absent. Ambiguous IDs or invalid updates raise
    ValueError before writing; a record's identity cannot be changed.
    """
    if not isinstance(record_id, str) or not record_id.strip():
        raise ValueError("record_id 必须是非空字符串。")
    if not isinstance(updates, dict):
        raise ValueError("更新内容必须是字典。")
    if "record_id" in updates and updates["record_id"] != record_id:
        raise ValueError("不能修改 record_id。")
    with _SAVE_LOCK:
        records = load_records()
        matches = [index for index, record in enumerate(records)
                   if isinstance(record, dict) and record.get("record_id") == record_id]
        if not matches:
            return False
        if len(matches) > 1:
            raise ValueError("存在重复 record_id，不能确定要更新的记录。")
        index = matches[0]
        updated = {**records[index], **updates}
        validate_record(updated)
        records[index] = updated
        _write_records(records)
        return True


def _write_records(records):
    # 先完成序列化，写入失败时仍保留原文件。
    content = json.dumps(records, ensure_ascii=False, indent=4)
    path = _record_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".records-", suffix=".tmp", delete=False
        ) as file:
            temporary_path = Path(file.name)
            file.write(content)
        # Windows 上先关闭临时文件，再原子替换目标文件。
        # Windows readers/scanners can briefly deny replacement even after close.
        # Retry only permission failures, with a maximum total backoff of 150 ms.
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
