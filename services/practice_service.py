"""Widget-independent practice state; drafts survive Streamlit widget cleanup."""


def clear_diagnosis(state):
    state["diagnosis"] = None
    state["diagnosis_problem_id"] = None
    state["diagnosed_code"] = None
    state["diagnosis_record_id"] = None
    state["hint_level"] = 1


def select_problem(state, problem):
    drafts = state.setdefault("drafts", {})
    problem_id = problem["id"]
    if state.get("selected_problem_id") != problem_id:
        clear_diagnosis(state)
        state["selected_problem_id"] = problem_id
    return drafts.setdefault(str(problem_id), problem["python_template"])


def save_draft(state, problem_id, code):
    state.setdefault("drafts", {})[str(problem_id)] = code


def set_diagnosis(state, problem_id, code, diagnosis, record_id=None):
    state["diagnosis"] = diagnosis
    state["diagnosis_problem_id"] = problem_id
    state["diagnosed_code"] = code
    state["diagnosis_record_id"] = record_id
    state["hint_level"] = 1


def reveal_next_hint(state):
    diagnosis = state.get("diagnosis") or {}
    total = len(diagnosis.get("hints", []))
    state["hint_level"] = min(state.get("hint_level", 1) + 1, max(total, 1))
    return state["hint_level"]
