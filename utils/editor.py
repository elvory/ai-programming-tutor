"""Ace editor wrapper that keeps drafts in plain session state.

Production rendering uses ``streamlit-code-editor`` (Ace + react-ace). The
component's value is a dictionary, so the practice page keeps a separate
string key as the canonical draft. Reading the component payload before
rendering also restores edits after a page switch when the blur event arrived
while another page was active.
"""

import streamlit as st

EVENT_TYPES = ("change", "blur", "submit")
DEFAULT_HEIGHT = "560px"


def widget_key(editor_key):
    """Return the component key derived from the canonical draft key."""
    return f"{editor_key}__ace"


def _event_text(event):
    """Extract code from a real editor event; ignore the default payload."""
    if not isinstance(event, dict) or event.get("type") not in EVENT_TYPES:
        return None
    text = event.get("text")
    return text if isinstance(text, str) else None


def render_code_editor(code, *, key, height=DEFAULT_HEIGHT):
    """Render an Ace editor and return the latest code string.

    ``key`` is the canonical session-state key holding a string. The editor
    uses a derived component key so its dictionary payload cannot overwrite
    the draft. ``allow_reset`` stays False so diagnostics, hints, and other
    reruns never reset the buffer; a state change only reaches the editor
    through this function's return value.

    The component reports on edit (debounced by the editor) and on blur.
    This keeps the canonical draft current even when navigation happens in
    the same interaction as the editor losing focus. ``allow_reset`` stays
    False so the reruns themselves never rewrite the buffer.
    """
    try:
        from code_editor import code_editor
    except ImportError as exc:  # pragma: no cover - exercised only without the dependency
        raise ImportError(
            "缺少代码编辑器依赖 streamlit-code-editor，请先执行 pip install -r requirements.txt。"
        ) from exc

    component_key = widget_key(key)
    stored = _event_text(st.session_state.get(component_key))
    latest = code if stored is None else stored

    response = code_editor(
        latest,
        lang="python",
        theme="dark",
        shortcuts="vscode",
        height=height,
        response_mode=["debounce", "blur"],
        allow_reset=False,
        props={"showGutter": True, "debounceChangePeriod": 800},
        options={"showLineNumbers": True, "tabSize": 4, "wrap": False, "displayIndentGuides": True},
        key=component_key,
    )
    event_text = _event_text(response)
    return latest if event_text is None else event_text
