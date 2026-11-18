"""Mock API трекера задач (task_171-174).

Поддерживает ограниченную модель статусов, идемпотентность по externalRef и
расчёт нарушений SLA.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

API_KEY = "mock-tracker-key"
TRANSITIONS = {
    "new": {"in_progress", "closed"},
    "in_progress": {"blocked", "resolved", "closed"},
    "blocked": {"in_progress", "resolved"},
    "resolved": {"closed", "in_progress"},
    "closed": set(),
}

app = FastAPI(title="Mock Tracker API", version="1.0.0")

ISSUES: Dict[str, dict] = {}
COMMENTS: Dict[str, List[dict]] = {}


class IssueIn(BaseModel):
    external_ref: str = Field(..., description="Ссылка на объект 1С (РИХ_Инцидент)")
    title: str
    description: Optional[str] = None
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")
    assignee: Optional[str] = None
    due_in_hours: int = Field(24, gt=0)


class IssuePatch(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None
    due_at: Optional[datetime] = None


class CommentIn(BaseModel):
    author: str
    text: str


def _check(x_api_key: Optional[str]) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="неверный или отсутствующий X-Api-Key")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mock_tracker_api", "issues": len(ISSUES)}


@app.post("/api/v1/issues", status_code=201)
def create_issue(payload: IssueIn, x_api_key: Optional[str] = Header(default=None)) -> dict:
    _check(x_api_key)
    now = datetime.now(timezone.utc)
    existing = next((i for i in ISSUES.values() if i["externalRef"] == payload.external_ref), None)
    if existing:
        return {**existing, "duplicate": True}

    issue = {
        "issueId": str(uuid.uuid4()),
        "externalRef": payload.external_ref,
        "title": payload.title,
        "description": payload.description,
        "priority": payload.priority,
        "status": "new",
        "assignee": payload.assignee,
        "createdAt": now.isoformat(),
        "dueAt": (now + timedelta(hours=payload.due_in_hours)).isoformat(),
        "duplicate": False,
    }
    ISSUES[issue["issueId"]] = issue
    COMMENTS[issue["issueId"]] = []
    return issue


@app.get("/api/v1/issues")
def list_issues(
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    due_before: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=500),
    x_api_key: Optional[str] = Header(default=None),
) -> dict:
    _check(x_api_key)
    items = list(ISSUES.values())
    if status:
        items = [i for i in items if i["status"] == status]
    if assignee:
        items = [i for i in items if i["assignee"] == assignee]
    if due_before:
        items = [i for i in items if datetime.fromisoformat(i["dueAt"]) <= due_before]
    return {"total": len(items), "items": items[:limit]}


@app.get("/api/v1/issues/{issue_id}")
def get_issue(issue_id: str, x_api_key: Optional[str] = Header(default=None)) -> dict:
    _check(x_api_key)
    issue = ISSUES.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail=f"задача {issue_id} не найдена")
    return {**issue, "comments": COMMENTS.get(issue_id, [])}


@app.patch("/api/v1/issues/{issue_id}")
def patch_issue(issue_id: str, payload: IssuePatch, x_api_key: Optional[str] = Header(default=None)) -> dict:
    _check(x_api_key)
    issue = ISSUES.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail=f"задача {issue_id} не найдена")

    if payload.status and payload.status != issue["status"]:
        allowed = TRANSITIONS.get(issue["status"], set())
        if payload.status not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"переход {issue['status']} → {payload.status} недопустим; "
                       f"разрешено: {', '.join(sorted(allowed)) or 'нет'}",
            )
        issue["status"] = payload.status
        if payload.status == "resolved":
            issue["resolvedAt"] = datetime.now(timezone.utc).isoformat()
    if payload.assignee is not None:
        issue["assignee"] = payload.assignee
    if payload.due_at is not None:
        issue["dueAt"] = payload.due_at.isoformat()
    return issue


@app.post("/api/v1/issues/{issue_id}/comments", status_code=201)
def add_comment(issue_id: str, payload: CommentIn, x_api_key: Optional[str] = Header(default=None)) -> dict:
    _check(x_api_key)
    if issue_id not in ISSUES:
        raise HTTPException(status_code=404, detail=f"задача {issue_id} не найдена")
    comment = {"author": payload.author, "text": payload.text,
               "createdAt": datetime.now(timezone.utc).isoformat()}
    COMMENTS.setdefault(issue_id, []).append(comment)
    return comment


@app.get("/api/v1/sla")
def sla_report(x_api_key: Optional[str] = Header(default=None)) -> dict:
    """Нарушения SLA: задачи, срок которых истёк, а статус не closed/resolved."""
    _check(x_api_key)
    now = datetime.now(timezone.utc)
    breached = []
    for issue in ISSUES.values():
        due = datetime.fromisoformat(issue["dueAt"])
        if issue["status"] in ("closed", "resolved"):
            continue
        if due < now:
            breached.append({**issue, "overdueHours": round((now - due).total_seconds() / 3600, 1)})
    breached.sort(key=lambda item: -item["overdueHours"])
    return {"checkedAt": now.isoformat(), "total": len(breached), "items": breached}
