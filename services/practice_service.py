"""Widget-independent practice state; drafts survive Streamlit widget cleanup."""

from uuid import uuid4

from services.language_service import validate_language


def draft_key(problem_id, language="python"):
    """Keep legacy Python keys; other languages occupy independent slots."""
    language = validate_language(language)
    return str(problem_id) if language == "python" else f"{problem_id}:{language}"


def clear_diagnosis(state):
    state["diagnosis"] = None
    state["diagnosis_problem_id"] = None
    state["diagnosed_code"] = None
    state["diagnosis_language"] = None
    state["diagnosis_record_id"] = None
    state["hint_level"] = 1
    state["pending_diagnosis"] = None


def select_problem(state, problem, language="python"):
    language = validate_language(language)
    drafts = state.setdefault("drafts", {})
    problem_id = problem["id"]
    if (state.get("selected_problem_id") != problem_id
            or state.get("selected_language", "python") != language):
        clear_diagnosis(state)
        state["selected_problem_id"] = problem_id
    state["selected_language"] = language
    template = problem["python_template"] if language == "python" else problem["templates"][language]
    return drafts.setdefault(draft_key(problem_id, language), template)


def save_draft(state, problem_id, code, language="python"):
    language = validate_language(language)
    state.setdefault("drafts", {})[draft_key(problem_id, language)] = code
    pending = state.get("pending_diagnosis")
    changed_result = (
        state.get("diagnosis") is not None
        and state.get("diagnosis_problem_id") == problem_id
        and state.get("diagnosis_language", "python") == language
        and state.get("diagnosed_code") != code
    )
    changed_request = (
        isinstance(pending, dict) and pending.get("problem_id") == problem_id
        and pending.get("language", "python") == language
        and pending.get("code") != code
    )
    if changed_result or changed_request:
        clear_diagnosis(state)


def begin_diagnosis(state, problem_id, code, language="python"):
    """Create a unique snapshot; starting again invalidates every older request."""
    clear_diagnosis(state)
    request = {"request_id": uuid4().hex, "problem_id": problem_id, "code": code,
               "language": validate_language(language)}
    state["pending_diagnosis"] = dict(request)
    return request


def diagnosis_request_is_current(state, request):
    """Check the request against both saved drafts and unsaved widget changes."""
    if not isinstance(request, dict) or not request.get("request_id"):
        return False
    if state.get("pending_diagnosis") != request:
        return False
    problem_id, code = request.get("problem_id"), request.get("code")
    language = request.get("language", "python")
    if state.get("selected_problem_id") != problem_id:
        return False
    if state.get("selected_language", "python") != language:
        return False
    if state.get("drafts", {}).get(draft_key(problem_id, language)) != code:
        return False
    if "problem_picker" in state and state["problem_picker"] != problem_id:
        return False
    editor_key = f"code_editor_{draft_key(problem_id, language)}"
    return editor_key not in state or state[editor_key] == code


def set_diagnosis(state, problem_id, code, diagnosis, record_id=None, language="python"):
    state["diagnosis"] = diagnosis
    state["diagnosis_problem_id"] = problem_id
    state["diagnosed_code"] = code
    state["diagnosis_language"] = validate_language(language)
    state["diagnosis_record_id"] = record_id
    state["hint_level"] = 1
    state["pending_diagnosis"] = None


def reveal_next_hint(state):
    diagnosis = state.get("diagnosis") or {}
    total = len(diagnosis.get("hints", []))
    state["hint_level"] = min(state.get("hint_level", 1) + 1, max(total, 1))
    return state["hint_level"]
