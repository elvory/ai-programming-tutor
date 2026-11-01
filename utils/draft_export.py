"""Explicit bridge from a live Streamlit session to the new browser workbench."""
from datetime import datetime, timezone
import json

from utils.editor import _event_text, widget_key


def build_draft_export(state):
    """Return only draft buffers; do not mutate state or touch the filesystem."""
    drafts = {str(key): value for key, value in state.get("drafts", {}).items()
              if str(key).isdigit() and isinstance(value, str)}
    for problem_id in list(drafts):
        editor_key = f"code_editor_{problem_id}"
        canonical = state.get(editor_key)
        if isinstance(canonical, str):
            drafts[problem_id] = canonical
        event = _event_text(state.get(widget_key(editor_key)))
        if event is not None:
            drafts[problem_id] = event
    return json.dumps({"schema_version": 1, "drafts": drafts,
                       "exported_at": datetime.now(timezone.utc).isoformat()},
                      ensure_ascii=False, indent=2)
