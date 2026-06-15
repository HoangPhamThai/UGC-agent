# agents/app/main.py
import logging
import sys
from functools import lru_cache
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent_service import AgentService
from app.errors import AgentServiceError
from app.schema import Artifact, MessageData, MessageRequest, ReviewJobData, ReviewRequest

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

app = FastAPI(title="UGC Agent Service", version="1.0.0")

# CORS — the browser calls this service cross-origin from the frontend; without
# this the preflight OPTIONS /api/v1/message returns 405 and responses lack the
# Access-Control-Allow-* headers. Mirrors the backend's middleware config.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def get_agent_service() -> AgentService:
    # Lazy import keeps agent_framework out of the module import graph, so the test
    # suite and `import app.main` need no framework install.
    from app.llm_agent import build_agent_service
    return build_agent_service()


@lru_cache
def get_review_service():
    # Lazy import keeps agent_framework out of the module import graph, so the test
    # suite and `import app.main` need no framework install.
    from app.llm_agent import build_review_service
    return build_review_service()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def _bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication")
    token = authorization[len("Bearer "):]
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication")
    return token


@app.post("/api/v1/message")
async def message(
    body: MessageRequest,
    authorization: Optional[str] = Header(default=None),
    svc: AgentService = Depends(get_agent_service),
) -> dict:
    jwt = _bearer_token(authorization)
    result = await svc.handle_message(jwt=jwt, session_id=body.session_id, user_text=body.message)
    artifact = (
        Artifact(title=result.artifact.title, markdown=result.artifact.markdown)
        if result.artifact
        else None
    )
    data = MessageData(session_id=body.session_id, reply=result.text, artifact=artifact)
    return {"success": True, "data": data.model_dump()}


@app.post("/api/v1/review")
async def review(
    body: ReviewRequest,
    background: BackgroundTasks,
    authorization: Optional[str] = Header(default=None),
    svc=Depends(get_review_service),
) -> dict:
    jwt = _bearer_token(authorization)
    job_id, key = await svc.start(
        jwt=jwt, article_id=body.article_id, workspace_id=body.workspace_id, rubrics=body.rubrics
    )
    background.add_task(
        svc.run,
        key=key, job_id=job_id, rubrics=body.rubrics,
        current_content=body.current_content, previous_content=body.previous_content,
        feedbacks=[fb.model_dump() for fb in body.feedbacks],
    )
    data = ReviewJobData(job_id=job_id)
    return {"success": True, "data": data.model_dump()}


def _envelope(message: str) -> dict:
    return {"success": False, "message": message}


@app.exception_handler(AgentServiceError)
async def _agent_error_handler(request: Request, exc: AgentServiceError):
    return JSONResponse(status_code=exc.status_code, content=_envelope(str(exc)))


@app.exception_handler(HTTPException)
async def _http_error_handler(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content=_envelope(message))


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=_envelope("Invalid request"))
