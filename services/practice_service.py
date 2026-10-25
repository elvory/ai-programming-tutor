"""Widget-independent practice state; drafts survive Streamlit widget cleanup."""

from uuid import uuid4


def clear_diagnosis(state):
    state["diagnosis"] = None
    state["diagnosis_problem_id"] = None
    state["diagnosed_code"] = None
    state["diagnosis_record_id"] = None
    state["hint_level"] = 1
    state["pending_diagnosis"] = None


def select_problem(state, problem):
    drafts = state.setdefault("drafts", {})
    problem_id = problem["id"]
    if state.get("selected_problem_id") != problem_id:
        clear_diagnosis(state)
        state["selected_problem_id"] = problem_id
    return drafts.setdefault(str(problem_id), problem["python_template"])


def save_draft(state, problem_id, code):
    state.setdefault("drafts", {})[str(problem_id)] = code
    pending = state.get("pending_diagnosis")
    changed_result = (
        state.get("diagnosis") is not None
        and state.get("diagnosis_problem_id") == problem_id
        and state.get("diagnosed_code") != code
    )
    changed_request = (
        isinstance(pending, dict) and pending.get("problem_id") == problem_id
        and pending.get("code") != code
    )
    if changed_result or changed_request:
        clear_diagnosis(state)


def begin_diagnosis(state, problem_id, code):
    """Create a unique snapshot; starting again invalidates every older request."""
    clear_diagnosis(state)
    request = {"request_id": uuid4().hex, "problem_id": problem_id, "code": code}
    state["pending_diagnosis"] = dict(request)
    return request


def diagnosis_request_is_current(state, request):
    """Check the request against both saved drafts and unsaved widget changes."""
    if not isinstance(request, dict) or not request.get("request_id"):
        return False
    if state.get("pending_diagnosis") != request:
        return False
    problem_id, code = request.get("problem_id"), request.get("code")
    if state.get("selected_problem_id") != problem_id:
        return False
    if state.get("drafts", {}).get(str(problem_id)) != code:
        return False
    if "problem_picker" in state and state["problem_picker"] != problem_id:
        return False
    editor_key = f"code_editor_{problem_id}"
    return editor_key not in state or state[editor_key] == code


def set_diagnosis(state, problem_id, code, diagnosis, record_id=None):
    state["diagnosis"] = diagnosis
    state["diagnosis_problem_id"] = problem_id
    state["diagnosed_code"] = code
    state["diagnosis_record_id"] = record_id
    state["hint_level"] = 1
    state["pending_diagnosis"] = None


def reveal_next_hint(state):
    diagnosis = state.get("diagnosis") or {}
    total = len(diagnosis.get("hints", []))
    state["hint_level"] = min(state.get("hint_level", 1) + 1, max(total, 1))
    return state["hint_level"]
