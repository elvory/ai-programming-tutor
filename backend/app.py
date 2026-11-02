"""Thin local HTTP adapter; business rules remain in ``services``.

The browser persists drafts. Short-lived per-tab workspaces use the existing
practice state machine for stale-result checks and progressive hints. Diagnosis
is deliberately two-phase: the model response cannot become a history record
until the browser confirms that its code/problem snapshot is still current.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock, RLock
from time import monotonic
from typing import Literal, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from services.activity_service import (SHANGHAI, build_heatmap, load_activities,
                                       mark_accepted, record_submission, summarize_activity)
from services.history_service import build_activity_rows, build_history_rows
from services.capability_service import build_capability_profile
from services.llm_service import DiagnosisError, analyze_code, normalize_diagnosis
from services.practice_service import (begin_diagnosis, clear_diagnosis, diagnosis_request_is_current, draft_key,
                                      reveal_next_hint, save_draft, select_problem, set_diagnosis)
from services.problem_service import get_learning_route, get_problem, load_problems, search_problems
from services.record_service import load_records, save_record, update_record


class Snapshot(BaseModel):
    workspace_id: UUID
    problem_id: int = Field(gt=0, strict=True)
    code: str
    revision: int = Field(ge=0, strict=True)
    language: Literal["python", "java", "c", "cpp"] = "python"


class Acceptance(BaseModel):
    workspace_id: UUID
    request_id: str = Field(min_length=1)
    revision: int = Field(ge=0, strict=True)


class HintRequest(BaseModel):
    workspace_id: UUID
    diagnosis_id: str = Field(min_length=1)
    revision: int = Field(ge=0, strict=True)
    expected_hint_level: Optional[int] = Field(default=None, ge=1, le=3, strict=True)


class Submission(Snapshot):
    submission_id: UUID


class AcceptedProblem(BaseModel):
    problem_id: int = Field(gt=0, strict=True)
    confirmed: bool = Field(strict=True)
    event_id: UUID
    language: Literal["python", "java", "c", "cpp"] = "python"


@dataclass
class Workspace:
    state: dict = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock)
    revision: int = -1
    candidate: Optional[dict] = None
    diagnosis_id: Optional[str] = None
    accepted_request_id: Optional[str] = None
    accepted_revision: int = -1
    warning: Optional[str] = None
    users: int = 0
    touched: float = field(default_factory=monotonic)


class Workspaces:
    """Bound memory; never evict an entry while an endpoint is using it."""
    def __init__(self, limit=512):
        self.limit = limit
        self.entries = {}
        self.lock = Lock()

    @contextmanager
    def lease(self, identity, *, create=True):
        key = str(identity)
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                if not create:
                    raise HTTPException(409, "辅导会话已过期，请重新诊断。代码草稿仍保存在浏览器中。")
                if len(self.entries) >= self.limit:
                    idle = [(old.touched, old_key) for old_key, old in self.entries.items() if old.users == 0]
                    if not idle:
                        raise HTTPException(503, "当前辅导请求较多，请稍后重试。")
                    del self.entries[min(idle)[1]]
                entry = self.entries[key] = Workspace()
            entry.users += 1
            entry.touched = monotonic()
        try:
            yield entry
        finally:
            with self.lock:
                entry.users -= 1
                entry.touched = monotonic()


def _problem(problem_id):
    problem = get_problem(problem_id)
    if problem is None:
        raise HTTPException(404, "未找到这道题，请重新选择。")
    return problem


def _stale():
    return HTTPException(409, "题目、语言、代码或请求已更新，本次过时结果已丢弃。")


def _sync(entry, snapshot, problem):
    """Called under a workspace lock; stale browser messages cannot roll back state."""
    template = (problem.get("python_template") if snapshot.language == "python"
                else problem.get("templates", {}).get(snapshot.language))
    if not isinstance(template, str) or not template.strip():
        # Custom catalogs may intentionally contain only their legacy Python
        # template. Reject before clearing a valid existing workspace result.
        raise HTTPException(422, "当前题目暂未提供所选语言的模板，请选择已有模板的语言。")
    if snapshot.revision < entry.revision:
        raise _stale()
    same_input = (entry.state.get("selected_problem_id") == snapshot.problem_id
                  and entry.state.get("selected_language", "python") == snapshot.language
                  and entry.state.get("drafts", {}).get(draft_key(snapshot.problem_id, snapshot.language)) == snapshot.code)
    if snapshot.revision == entry.revision and not same_input:
        raise _stale()
    if snapshot.revision > entry.revision:
        # A new edit intent invalidates the diagnosis even when its source
        # happens to match. This also covers A -> B -> A messages arriving as
        # rev3(A), rev2(B), where the intermediate edit is rejected as stale.
        clear_diagnosis(entry.state)
        entry.candidate = None
        entry.diagnosis_id = None
        entry.accepted_request_id = None
        entry.accepted_revision = -1
        entry.warning = None
    select_problem(entry.state, problem, language=snapshot.language)
    save_draft(entry.state, snapshot.problem_id, snapshot.code, language=snapshot.language)
    entry.revision = snapshot.revision
    if entry.state.get("diagnosis") is None:
        entry.diagnosis_id = None
        entry.accepted_request_id = None
        entry.warning = None


def _public_diagnosis(entry):
    diagnosis = dict(entry.state["diagnosis"])
    level = entry.state["hint_level"]
    total = len(diagnosis["hints"])
    diagnosis["hints"] = diagnosis["hints"][:level]
    return {"diagnosis": diagnosis, "diagnosis_id": entry.diagnosis_id,
            "record_id": entry.state.get("diagnosis_record_id"), "hint_level": level,
            "hint_count": total, "warning": entry.warning,
            "language": entry.state.get("diagnosis_language", "python")}


def create_app(*, workspace_limit=512):
    app = FastAPI(title="AI Programming Tutor", version="3.0", docs_url=None, redoc_url=None)
    workspaces = Workspaces(workspace_limit)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _error):
        return JSONResponse(status_code=422, content={"detail": "请求参数不完整或格式不正确，请检查后重试。"})

    @app.exception_handler(ValueError)
    @app.exception_handler(OSError)
    async def data_error(_request, _error):
        return JSONResponse(status_code=503, content={"detail": "本地数据暂时无法读取或保存，请检查文件格式与权限。原数据未被覆盖。"})

    @app.get("/api/health")
    def health():
        return {"ok": True, "execution_available": False}

    @app.get("/api/bootstrap")
    def bootstrap():
        problems = load_problems()
        activities = load_activities()
        return {"problems": problems, "route": get_learning_route(),
                "summary": summarize_activity(activities, problems), "heatmap": build_heatmap(activities),
                "capability": build_capability_profile(activities, problems)}

    @app.get("/api/capabilities")
    def capabilities():
        return build_capability_profile(load_activities(), load_problems())

    @app.get("/api/problems/{problem_id}")
    def problem_detail(problem_id: int):
        return _problem(problem_id)

    @app.get("/api/problems")
    def problems(query: str = "", difficulty: Optional[str] = None, tags: list[str] = Query(default=[])):
        return {"problems": search_problems(query=query, difficulty=difficulty or None, tags=tags)}

    @app.get("/api/history")
    def history(problem_id: Optional[int] = Query(default=None, gt=0)):
        records = load_records()
        activities = load_activities()
        record_rows = build_history_rows(records, activities)
        activity_rows = build_activity_rows(activities)
        if problem_id is not None:
            record_rows = [row for row in record_rows if row.get("LeetCode 题号") == str(problem_id)]
            activity_rows = [row for row in activity_rows if row.get("LeetCode 题号") == str(problem_id)]
        return {"records": record_rows, "activities": activity_rows}

    @app.post("/api/workspace/sync")
    def sync(snapshot: Snapshot):
        problem = _problem(snapshot.problem_id)
        with workspaces.lease(snapshot.workspace_id) as entry, entry.lock:
            _sync(entry, snapshot, problem)
        return {"revision": snapshot.revision, "problem_id": snapshot.problem_id, "language": snapshot.language}

    @app.post("/api/diagnoses")
    def diagnose(snapshot: Snapshot):
        problem = _problem(snapshot.problem_id)
        if not snapshot.code.strip():
            raise HTTPException(422, "请先填写代码，再请求诊断。")
        # The registry lease stays live during the call; only the per-workspace
        # lock is released so edits/new requests can invalidate this snapshot.
        with workspaces.lease(snapshot.workspace_id) as entry:
            with entry.lock:
                _sync(entry, snapshot, problem)
                request = begin_diagnosis(entry.state, snapshot.problem_id, snapshot.code, language=snapshot.language)
                entry.candidate = None
                entry.diagnosis_id = None
                entry.accepted_request_id = None
                entry.warning = None
            try:
                result = normalize_diagnosis(analyze_code(snapshot.code, problem, language=snapshot.language))
                if (result is None or result.get("source") != "deepseek"
                        or result.get("is_mock") is not False):
                    raise DiagnosisError("未获得完整有效的 DeepSeek 诊断结果。")
            except Exception as error:
                with entry.lock:
                    if diagnosis_request_is_current(entry.state, request):
                        clear_diagnosis(entry.state)
                message = str(error) if isinstance(error, DiagnosisError) else "诊断未能完成，请保留草稿后重试。"
                raise HTTPException(502, message) from None
            with entry.lock:
                if (entry.revision != snapshot.revision
                        or not diagnosis_request_is_current(entry.state, request)):
                    raise _stale()
                entry.candidate = {"request": request, "revision": snapshot.revision,
                                   "diagnosis": result, "problem": problem}
            return {"request_id": request["request_id"], "revision": snapshot.revision}

    @app.post("/api/diagnoses/accept")
    def accept_diagnosis(acceptance: Acceptance):
        with workspaces.lease(acceptance.workspace_id, create=False) as entry, entry.lock:
            if acceptance.revision != entry.revision:
                raise _stale()
            if (entry.accepted_request_id == acceptance.request_id
                    and entry.accepted_revision == acceptance.revision
                    and entry.state.get("diagnosis") is not None):
                return _public_diagnosis(entry)
            candidate = entry.candidate
            if (candidate is None or candidate["revision"] != acceptance.revision
                    or candidate["request"]["request_id"] != acceptance.request_id
                    or not diagnosis_request_is_current(entry.state, candidate["request"])):
                raise _stale()
            result, problem, request = candidate["diagnosis"], candidate["problem"], candidate["request"]
            record_id = str(uuid4())
            record = {
                "question": f"#{problem['id']} {problem['title_zh']}：{problem['summary']}",
                "error_type": result["error_type"], "knowledge": result["knowledge"], "hint_level": 1,
                "record_id": record_id, "leetcode_id": problem["id"], "title": problem["title_zh"],
                "created_at": datetime.now(SHANGHAI).isoformat(), "hints_used": [1],
                "source": result["source"], "is_mock": result["is_mock"], "model": result.get("model"),
                "language": request["language"],
            }
            try:
                save_record(record)
            except (OSError, ValueError, TypeError):
                record_id = None
                entry.warning = "诊断已完成，但诊断记录保存失败。请检查记录文件格式和写入权限。"
            set_diagnosis(entry.state, problem["id"], request["code"], result, record_id, language=request["language"])
            entry.diagnosis_id = str(uuid4())
            entry.accepted_request_id = acceptance.request_id
            entry.accepted_revision = acceptance.revision
            entry.candidate = None
            return _public_diagnosis(entry)

    @app.post("/api/hints")
    def hint(payload: HintRequest):
        with workspaces.lease(payload.workspace_id, create=False) as entry, entry.lock:
            if (entry.revision != payload.revision or entry.diagnosis_id != payload.diagnosis_id
                    or entry.state.get("diagnosis") is None):
                raise _stale()
            if payload.expected_hint_level is not None:
                current = entry.state["hint_level"]
                if payload.expected_hint_level < current:
                    # A successful response may have been lost; retrying the
                    # same transition must not reveal an additional hint.
                    return _public_diagnosis(entry)
                if payload.expected_hint_level > current:
                    raise _stale()
            level = reveal_next_hint(entry.state)
            record_id = entry.state.get("diagnosis_record_id")
            if record_id is not None:
                try:
                    updated = update_record(record_id, {"hint_level": level, "hints_used": list(range(1, level + 1))})
                    if not updated:
                        entry.warning = "Hint 已展示，但使用情况未能保存。请检查诊断记录。"
                    else:
                        entry.warning = None
                except (OSError, ValueError, TypeError):
                    entry.warning = "Hint 已展示，但使用情况未能保存。请检查诊断记录。"
            return _public_diagnosis(entry)

    @app.post("/api/submissions")
    def submit(payload: Submission):
        problem = _problem(payload.problem_id)
        if not payload.code.strip():
            raise HTTPException(422, "请先填写代码，再记录本地提交。")
        with workspaces.lease(payload.workspace_id) as entry, entry.lock:
            _sync(entry, payload, problem)
            diagnosis = entry.state.get("diagnosis")
            fresh = diagnosis if (entry.state.get("diagnosis_problem_id") == payload.problem_id
                                   and entry.state.get("diagnosis_language") == payload.language
                                   and entry.state.get("diagnosed_code") == payload.code) else None
            record_submission(payload.problem_id, problem["title_zh"],
                              submission_id=str(payload.submission_id), diagnosis=fresh,
                              language=payload.language,
                              hints_used=list(range(1, entry.state["hint_level"] + 1)) if fresh else [])
        return {"ok": True}

    @app.post("/api/accepted")
    def accept_problem(payload: AcceptedProblem):
        problem = _problem(payload.problem_id)
        if not payload.confirmed:
            raise HTTPException(422, "请先确认这道题已在 LeetCode 提交并通过。")
        mark_accepted(problem["id"], problem["title_zh"], event_id=str(payload.event_id), language=payload.language)
        return {"ok": True}

    # The compiled frontend is optional during development. Vite proxies /api
    # to this app; a production build is served on the same local origin.
    frontend = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if (frontend / "index.html").is_file():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")

    return app


app = create_app()
