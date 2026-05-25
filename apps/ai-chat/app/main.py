"""FastAPI entrypoint for the AI agricultural assistant."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, cast
from uuid import uuid4

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, status
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.config import Settings, get_settings
from app.logging_config import configure_logging

SERVICE_NAME = "ai-chat"
REPLAY_WINDOW_SECONDS = 300
RATE_WINDOW_SECONDS = 60

logger = structlog.get_logger(SERVICE_NAME)


class AuthUser(BaseModel):
    user_id: str


class ChatSessionCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class ChatSession(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", min_length=2, max_length=20)


class ChatMessage(BaseModel):
    id: str
    session_id: str
    user_id: str
    role: Literal["user", "assistant"]
    content: str
    status: Literal["complete", "incomplete"] = "complete"
    created_at: datetime


class KnowledgeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    source: str = Field(default="manual", min_length=1, max_length=120)


class KnowledgeChunk(BaseModel):
    id: str
    title: str
    content: str
    source: str
    created_at: datetime


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "service starting",
        service=SERVICE_NAME,
        env=settings.app_env,
        port=settings.port,
    )
    try:
        yield
    finally:
        logger.info("service stopped cleanly", service=SERVICE_NAME)


app = FastAPI(title="khetibadi-ai-chat", lifespan=lifespan)
sessions: dict[str, ChatSession] = {}
messages: dict[str, list[ChatMessage]] = {}
knowledge_chunks: dict[str, KnowledgeChunk] = {}
rate_limits: dict[str, list[datetime]] = {}


def require_hmac_user(
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
    x_hmac_signature: Annotated[str | None, Header(alias="X-HMAC-Signature")] = None,
    x_timestamp: Annotated[str | None, Header(alias="X-Timestamp")] = None,
) -> AuthUser:
    settings = get_settings()
    if settings.hmac_secret == "":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "service_unavailable", "message": "HMAC secret is not configured"},
        )
    if x_user_id is None or x_hmac_signature is None or x_timestamp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "missing HMAC identity headers"},
        )
    try:
        timestamp = int(x_timestamp)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "invalid timestamp"},
        ) from exc
    if abs(time.time() - timestamp) > REPLAY_WINDOW_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "replay_detected",
                "message": "request timestamp is outside replay window",
            },
        )
    expected = hmac.new(
        settings.hmac_secret.encode(),
        f"{x_user_id}:{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_hmac_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "invalid HMAC signature"},
        )
    return AuthUser(user_id=x_user_id)


AuthDependency = Annotated[AuthUser, Depends(require_hmac_user)]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/ai/chat/health")
async def chat_health() -> dict[str, object]:
    settings = get_settings()
    llm_ready = settings.groq_api_key != "" or settings.ai_chat_allow_fake_llm
    return {
        "status": "ok" if llm_ready else "degraded",
        "service": SERVICE_NAME,
        "llm_mode": "groq" if settings.groq_api_key else "stub",
        "database": "in_memory",
        "redis": "in_memory",
    }


@app.post("/ai/chat/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(req: ChatSessionCreate, user: AuthDependency) -> dict[str, ChatSession]:
    now = datetime.now(UTC)
    session = ChatSession(
        id=str(uuid4()),
        user_id=user.user_id,
        title=req.title.strip(),
        created_at=now,
        updated_at=now,
    )
    sessions[session.id] = session
    messages[session.id] = []
    return {"session": session}


@app.get("/ai/chat/sessions")
async def list_sessions(user: AuthDependency) -> dict[str, list[ChatSession]]:
    visible = [session for session in sessions.values() if session.user_id == user.user_id]
    visible.sort(key=lambda session: session.updated_at, reverse=True)
    return {"sessions": visible}


@app.delete("/ai/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, user: AuthDependency) -> None:
    session = get_owned_session(session_id, user.user_id)
    del sessions[session.id]
    messages.pop(session.id, None)


@app.get("/ai/chat/sessions/{session_id}/messages")
async def list_messages(session_id: str, user: AuthDependency) -> dict[str, list[ChatMessage]]:
    session = get_owned_session(session_id, user.user_id)
    return {"messages": messages.get(session.id, [])}


@app.post("/ai/chat/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    req: ChatMessageRequest,
    user: AuthDependency,
) -> StreamingResponse:
    session = get_owned_session(session_id, user.user_id)
    enforce_rate_limit(user.user_id)
    now = datetime.now(UTC)
    user_message = ChatMessage(
        id=str(uuid4()),
        session_id=session.id,
        user_id=user.user_id,
        role="user",
        content=req.message.strip(),
        created_at=now,
    )
    messages.setdefault(session.id, []).append(user_message)
    session.updated_at = now
    return StreamingResponse(
        stream_response(session, user.user_id, req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/ai/chat/knowledge", status_code=status.HTTP_201_CREATED)
async def add_knowledge(req: KnowledgeRequest, _: AuthDependency) -> dict[str, KnowledgeChunk]:
    chunk = KnowledgeChunk(
        id=str(uuid4()),
        title=req.title.strip(),
        content=req.content.strip(),
        source=req.source.strip(),
        created_at=datetime.now(UTC),
    )
    knowledge_chunks[chunk.id] = chunk
    return {"chunk": chunk}


async def stream_response(
    session: ChatSession,
    user_id: str,
    req: ChatMessageRequest,
) -> AsyncIterator[str]:
    settings = get_settings()
    if settings.groq_api_key == "" and not settings.ai_chat_allow_fake_llm:
        yield sse_event("error", {"error": "llm_unavailable"})
        return
    token_count = 0
    response_parts: list[str] = []
    try:
        async for token in generate_assistant_tokens(settings, req):
            response_parts.append(token)
            yield sse_event("token", {"token": token, "index": token_count})
            token_count += 1
    except Exception as exc:
        partial = "".join(response_parts).strip()
        if partial != "":
            assistant = ChatMessage(
                id=str(uuid4()),
                session_id=session.id,
                user_id=user_id,
                role="assistant",
                content=partial,
                status="incomplete",
                created_at=datetime.now(UTC),
            )
            messages.setdefault(session.id, []).append(assistant)
            session.updated_at = assistant.created_at
        logger.warning("chat stream failed", error=str(exc), session_id=session.id)
        yield sse_event("error", {"error": "llm_stream_failed"})
        return
    response_text = "".join(response_parts).strip()
    assistant = ChatMessage(
        id=str(uuid4()),
        session_id=session.id,
        user_id=user_id,
        role="assistant",
        content=response_text,
        created_at=datetime.now(UTC),
    )
    messages.setdefault(session.id, []).append(assistant)
    session.updated_at = assistant.created_at
    yield sse_event(
        "done",
        {
            "message_id": assistant.id,
            "session_id": session.id,
            "total_tokens": token_count,
        },
    )


async def generate_assistant_tokens(
    settings: Settings,
    req: ChatMessageRequest,
) -> AsyncIterator[str]:
    if settings.groq_api_key != "":
        async for token in stream_groq_tokens(settings, req):
            yield token
        return
    response_text = build_stub_response(req.message, req.language)
    for token in response_text.split():
        yield f"{token} "


async def stream_groq_tokens(settings: Settings, req: ChatMessageRequest) -> AsyncIterator[str]:
    model = ChatGroq(
        model=settings.groq_model,
        max_tokens=settings.groq_max_tokens,
        temperature=0.2,
        timeout=30,
        max_retries=1,
    )
    system_prompt = build_system_prompt(req.language)
    async for chunk in model.astream(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=req.message.strip()),
        ]
    ):
        content = cast(str | list[str | dict[str, object]], chunk.content)
        if isinstance(content, str) and content != "":
            yield content


def build_system_prompt(language: str) -> str:
    relevant_titles = ", ".join(chunk.title for chunk in knowledge_chunks.values())
    knowledge = relevant_titles if relevant_titles else "No curated knowledge chunks are available."
    preferred_language = "Hindi" if language.lower().startswith("hi") else "English"
    return (
        "You are Khetibadi AI, an expert agricultural assistant for Indian farmers. "
        "Give practical, safe, locally relevant farm advice. Use concise steps, mention "
        "weather, soil moisture, pests, and mandi prices when relevant. If required context "
        "is unavailable, say so plainly and continue with general guidance. "
        f"Respond in {preferred_language}. Relevant knowledge titles: {knowledge}"
    )


def get_owned_session(session_id: str, user_id: str) -> ChatSession:
    session = sessions.get(session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "chat session not found"},
        )
    return session


def enforce_rate_limit(user_id: str) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    window_start = now - timedelta(seconds=RATE_WINDOW_SECONDS)
    recent = [seen_at for seen_at in rate_limits.get(user_id, []) if seen_at >= window_start]
    if len(recent) >= settings.chat_rate_limit_per_minute:
        rate_limits[user_id] = recent
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "rate_limited", "message": "chat rate limit exceeded"},
            headers={"Retry-After": str(RATE_WINDOW_SECONDS)},
        )
    recent.append(now)
    rate_limits[user_id] = recent


def build_stub_response(message: str, language: str) -> str:
    relevant_titles = ", ".join(chunk.title for chunk in knowledge_chunks.values())
    knowledge = f" Relevant knowledge: {relevant_titles}." if relevant_titles else ""
    if language.lower().startswith("hi"):
        return (
            "मैं Khetibadi AI हूँ। आपके सवाल के आधार पर व्यावहारिक सलाह: "
            "मिट्टी की नमी, स्थानीय मौसम और मंडी भाव देखकर निर्णय लें।"
            f" आपने पूछा: {message.strip()}.{knowledge}"
        )
    return (
        "I am Khetibadi AI. Practical guidance: check soil moisture, local weather, "
        "and current mandi prices before making the next farm decision. "
        f"You asked: {message.strip()}.{knowledge}"
    )


def sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
