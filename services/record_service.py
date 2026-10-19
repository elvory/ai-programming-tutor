import json
import os
from pathlib import Path
import tempfile
from threading import Lock

FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "records.json"
_SAVE_LOCK = Lock()


def load_records():
    """读取历史；损坏的数据应报错，避免保存时覆盖原有记录。"""
    path = Path(FILE_PATH)
    try:
        with path.open("r", encoding="utf-8") as file:
            records = json.load(file)
    except FileNotFoundError:
        return []

    if not isinstance(records, list):
        raise ValueError("学习记录文件的 JSON 根节点必须是列表。")
    return records


def save_record(record):
    # Streamlit 同一进程的会话可能并发保存，锁住完整的读取和写入操作。
    with _SAVE_LOCK:
        _save_record(record)


def _save_record(record):
    records = load_records()
    records.append(record)
    # 先完成序列化，写入失败时仍保留原文件。
    content = json.dumps(records, ensure_ascii=False, indent=4)
    path = Path(FILE_PATH)
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
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
