"""FastAPI entrypoint for the AI agricultural assistant."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, cast
from uuid import uuid4

import httpx
import redis.asyncio as redis
import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile, status
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.config import Settings, get_settings
from app.logging_config import configure_logging

SERVICE_NAME = "ai-chat"
REPLAY_WINDOW_SECONDS = 300
RATE_WINDOW_SECONDS = 60
CONTEXT_TIMEOUT_SECONDS = 2
MAX_TOOL_ROUNDS = 1
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TOOL_RESULT_CHARS = 3000
MAX_RECENT_CHAT_MESSAGES = 8
ChatChannel = Literal["dashboard", "whatsapp"]

logger = structlog.get_logger(SERVICE_NAME)
db_pool: AsyncConnectionPool | None = None
redis_client: redis.Redis | None = None


class AuthUser(BaseModel):
    user_id: str


class ChatSessionCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)
    channel: ChatChannel = "dashboard"
    external_thread_id: str | None = Field(default=None, max_length=180)


class ChatSession(BaseModel):
    id: str
    user_id: str
    title: str
    channel: ChatChannel = "dashboard"
    external_thread_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", min_length=2, max_length=20)


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", min_length=2, max_length=20)
    account_name: str | None = Field(default=None, max_length=120)


class BridgeMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", min_length=2, max_length=20)
    channel: Literal["whatsapp"] = "whatsapp"
    external_thread_id: str = Field(min_length=1, max_length=180)
    account_name: str | None = Field(default=None, max_length=120)
    title: str = Field(default="WhatsApp conversation", min_length=1, max_length=120)


class BridgeMessageResponse(BaseModel):
    session_id: str
    message_id: str
    response: str
    status: Literal["complete", "incomplete"]


class ChatMessage(BaseModel):
    id: str
    session_id: str
    user_id: str
    channel: ChatChannel = "dashboard"
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


class ChatAttachment(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    data: bytes


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
    await initialize_storage(settings)
    try:
        yield
    finally:
        await close_storage()
        logger.info("service stopped cleanly", service=SERVICE_NAME)


app = FastAPI(title="khetibadi-ai-chat", lifespan=lifespan)
sessions: dict[str, ChatSession] = {}
messages: dict[str, list[ChatMessage]] = {}
knowledge_chunks: dict[str, KnowledgeChunk] = {}
rate_limits: dict[str, list[datetime]] = {}


async def initialize_storage(settings: Settings) -> None:
    global db_pool, redis_client
    try:
        pool = AsyncConnectionPool(
            settings.database_url,
            open=False,
            min_size=1,
            max_size=4,
            kwargs={"row_factory": dict_row},
        )
        await pool.open()
        await ensure_database_schema(pool)
        db_pool = pool
        await load_knowledge_chunks()
    except Exception as exc:
        logger.warning("postgres chat storage unavailable", error=str(exc))
        if settings.chat_storage_required:
            raise
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        await cast(Awaitable[object], client.ping())
        redis_client = client
    except Exception as exc:
        logger.warning("redis chat rate limiter unavailable", error=str(exc))
        if settings.chat_storage_required:
            raise


async def close_storage() -> None:
    global db_pool, redis_client
    if db_pool is not None:
        await db_pool.close()
        db_pool = None
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


async def ensure_database_schema(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id UUID PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'dashboard',
                external_thread_id TEXT,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id UUID PRIMARY KEY,
                session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'dashboard',
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('complete', 'incomplete')),
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id UUID PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        await conn.execute("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS channel TEXT")
        await conn.execute(
            "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS external_thread_id TEXT"
        )
        await conn.execute("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS channel TEXT")
        await conn.execute("UPDATE chat_sessions SET channel = 'dashboard' WHERE channel IS NULL")
        await conn.execute("UPDATE chat_messages SET channel = 'dashboard' WHERE channel IS NULL")
        await conn.execute("ALTER TABLE chat_sessions ALTER COLUMN channel SET DEFAULT 'dashboard'")
        await conn.execute("ALTER TABLE chat_messages ALTER COLUMN channel SET DEFAULT 'dashboard'")
        await conn.execute("ALTER TABLE chat_sessions ALTER COLUMN channel SET NOT NULL")
        await conn.execute("ALTER TABLE chat_messages ALTER COLUMN channel SET NOT NULL")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS chat_sessions_user_updated_idx "
            "ON chat_sessions (user_id, updated_at DESC)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS chat_sessions_user_channel_thread_idx "
            "ON chat_sessions (user_id, channel, external_thread_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS chat_messages_session_created_idx "
            "ON chat_messages (session_id, created_at ASC)"
        )


async def load_knowledge_chunks() -> None:
    if db_pool is None:
        return
    async with db_pool.connection() as conn:
        rows = await conn.execute(
            """
            SELECT id::text, title, content, source, created_at
            FROM knowledge_chunks
            ORDER BY created_at DESC
            LIMIT 100
            """
        )
        loaded = [KnowledgeChunk.model_validate(row) async for row in rows]
    knowledge_chunks.clear()
    knowledge_chunks.update({chunk.id: chunk for chunk in loaded})


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
        "database": "postgres" if db_pool is not None else "in_memory",
        "redis": "redis" if redis_client is not None else "in_memory",
    }


@app.post("/ai/chat/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(req: ChatSessionCreate, user: AuthDependency) -> dict[str, ChatSession]:
    now = datetime.now(UTC)
    session = ChatSession(
        id=str(uuid4()),
        user_id=user.user_id,
        title=req.title.strip(),
        channel=req.channel,
        external_thread_id=req.external_thread_id,
        created_at=now,
        updated_at=now,
    )
    await save_session(session)
    return {"session": session}


@app.get("/ai/chat/sessions")
async def list_sessions(user: AuthDependency) -> dict[str, list[ChatSession]]:
    return {"sessions": await find_sessions(user.user_id)}


@app.delete("/ai/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, user: AuthDependency) -> None:
    session = await get_owned_session(session_id, user.user_id)
    await remove_session(session.id)


@app.get("/ai/chat/sessions/{session_id}/messages")
async def list_messages(session_id: str, user: AuthDependency) -> dict[str, list[ChatMessage]]:
    session = await get_owned_session(session_id, user.user_id)
    return {"messages": await find_messages(session.id)}


@app.post("/ai/chat/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: Request,
    user: AuthDependency,
) -> StreamingResponse:
    session = await get_owned_session(session_id, user.user_id)
    await enforce_rate_limit(user.user_id)
    agent_request, attachment = await parse_agent_request(request)
    now = datetime.now(UTC)
    user_message = ChatMessage(
        id=str(uuid4()),
        session_id=session.id,
        user_id=user.user_id,
        channel=session.channel,
        role="user",
        content=message_with_attachment_note(agent_request.message, attachment),
        created_at=now,
    )
    await save_message(user_message)
    session.updated_at = now
    await update_session_timestamp(session.id, now)
    recent_messages = await recent_chat_history(session.id, exclude_message_id=user_message.id)
    return StreamingResponse(
        stream_response(session, user.user_id, agent_request, attachment, recent_messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/ai/chat/internal/bridge/messages")
async def send_bridge_message(
    req: BridgeMessageRequest,
    user: AuthDependency,
) -> dict[str, BridgeMessageResponse]:
    settings = get_settings()
    try:
        response = await asyncio.wait_for(
            process_bridge_message(req, user.user_id),
            timeout=settings.bridge_ai_timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "ai_timeout", "message": "AI assistant timed out"},
        ) from exc
    return {"message": response}


async def process_bridge_message(
    req: BridgeMessageRequest,
    user_id: str,
) -> BridgeMessageResponse:
    settings = get_settings()
    if settings.groq_api_key == "" and not settings.ai_chat_allow_fake_llm:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "llm_unavailable", "message": "AI assistant is unavailable"},
        )
    await enforce_rate_limit(user_id)
    session = await find_or_create_bridge_session(user_id, req)
    now = datetime.now(UTC)
    user_message = ChatMessage(
        id=str(uuid4()),
        session_id=session.id,
        user_id=user_id,
        channel=req.channel,
        role="user",
        content=req.message.strip(),
        created_at=now,
    )
    await save_message(user_message)
    await update_session_timestamp(session.id, now)

    response_parts: list[str] = []
    response_status: Literal["complete", "incomplete"] = "complete"
    agent_request = AgentRequest(
        message=req.message,
        language=req.language,
        account_name=req.account_name,
    )
    try:
        recent_messages = await recent_chat_history(session.id, exclude_message_id=user_message.id)
        async for token in generate_assistant_tokens(
            settings, user_id, agent_request, None, recent_messages
        ):
            response_parts.append(token)
    except Exception as exc:
        response_status = "incomplete"
        logger.warning("bridge chat generation failed", error=str(exc), session_id=session.id)
    response_text = "".join(response_parts).strip()
    if response_text == "":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "ai_unavailable", "message": "AI assistant failed to respond"},
        )
    assistant = ChatMessage(
        id=str(uuid4()),
        session_id=session.id,
        user_id=user_id,
        channel=req.channel,
        role="assistant",
        content=response_text,
        status=response_status,
        created_at=datetime.now(UTC),
    )
    await save_message(assistant)
    await update_session_timestamp(session.id, assistant.created_at)
    return BridgeMessageResponse(
        session_id=session.id,
        message_id=assistant.id,
        response=response_text,
        status=response_status,
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
    await save_knowledge(chunk)
    return {"chunk": chunk}


async def stream_response(
    session: ChatSession,
    user_id: str,
    req: AgentRequest,
    attachment: ChatAttachment | None,
    recent_messages: list[ChatMessage],
) -> AsyncIterator[str]:
    settings = get_settings()
    if settings.groq_api_key == "" and not settings.ai_chat_allow_fake_llm:
        yield sse_event("error", {"error": "llm_unavailable"})
        return
    token_count = 0
    response_parts: list[str] = []
    try:
        async for token in generate_assistant_tokens(
            settings, user_id, req, attachment, recent_messages
        ):
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
                channel=session.channel,
                role="assistant",
                content=partial,
                status="incomplete",
                created_at=datetime.now(UTC),
            )
            await save_message(assistant)
            session.updated_at = assistant.created_at
            await update_session_timestamp(session.id, assistant.created_at)
        logger.warning("chat stream failed", error=str(exc), session_id=session.id)
        yield sse_event("error", {"error": "llm_stream_failed"})
        return
    response_text = "".join(response_parts).strip()
    assistant = ChatMessage(
        id=str(uuid4()),
        session_id=session.id,
        user_id=user_id,
        channel=session.channel,
        role="assistant",
        content=response_text,
        created_at=datetime.now(UTC),
    )
    await save_message(assistant)
    session.updated_at = assistant.created_at
    await update_session_timestamp(session.id, assistant.created_at)
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
    user_id: str,
    req: AgentRequest,
    attachment: ChatAttachment | None,
    recent_messages: list[ChatMessage] | None = None,
) -> AsyncIterator[str]:
    if settings.groq_api_key != "":
        async for token in stream_groq_tokens(
            settings, user_id, req, attachment, recent_messages or []
        ):
            yield token
        return
    response_text = build_stub_response(req.message, req.language)
    for token in response_text.split():
        yield f"{token} "


async def parse_agent_request(request: Request) -> tuple[AgentRequest, ChatAttachment | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        message = form.get("message")
        language = form.get("language", "en")
        image_value = form.get("image")
        attachment = await read_attachment(cast(UploadFile | None, image_value))
        return resolve_agent_request(
            str(message) if message is not None else None, str(language)
        ), attachment
    payload = await request.json()
    req = ChatMessageRequest.model_validate(payload)
    return AgentRequest(message=req.message, language=req.language), None


def resolve_agent_request(message: str | None, language: str) -> AgentRequest:
    if message is None or message.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation_error", "message": "message is required"},
        )
    return AgentRequest(message=message.strip(), language=language)


async def read_attachment(image: UploadFile | None) -> ChatAttachment | None:
    if image is None:
        return None
    data = await image.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": "payload_too_large", "message": "image must be 10MB or smaller"},
        )
    return ChatAttachment(
        filename=image.filename or "leaf-image",
        content_type=image.content_type or "application/octet-stream",
        size_bytes=len(data),
        data=data,
    )


def message_with_attachment_note(message: str, attachment: ChatAttachment | None) -> str:
    if attachment is None:
        return message.strip()
    attachment_note = (
        f"[attached image: {attachment.filename}, {attachment.content_type}, "
        f"{attachment.size_bytes} bytes]"
    )
    return f"{message.strip()}\n\n{attachment_note}"


def build_user_prompt(
    req: AgentRequest,
    attachment: ChatAttachment | None,
    tool_context: dict[str, object],
    recent_messages: list[ChatMessage],
) -> str:
    attachment_note = ""
    if attachment is not None:
        attachment_note = (
            f"\nAttached crop image: {attachment.filename} ({attachment.content_type}, "
            f"{attachment.size_bytes} bytes). Use detect_plant_disease if image diagnosis matters."
        )
    context_json = json.dumps(compact_tool_context(tool_context), default=str, ensure_ascii=False)[
        :MAX_TOOL_RESULT_CHARS
    ]
    history_text = render_recent_history(recent_messages)
    history_section = ""
    if history_text != "":
        history_section = f"\nRecent conversation in this thread:\n{history_text}"
    return (
        f"Farmer question: {req.message.strip()}{attachment_note}{history_section}\n"
        f"Preloaded farmer context: {context_json}"
    )


def render_recent_history(recent_messages: list[ChatMessage]) -> str:
    lines: list[str] = []
    for message in recent_messages[-MAX_RECENT_CHAT_MESSAGES:]:
        content = message.content.strip()
        if content == "":
            continue
        role = "Farmer" if message.role == "user" else "Khetibadi AI"
        lines.append(f"{role}: {content[:500]}")
    return "\n".join(lines)


def should_preload_market_data(message: str) -> bool:
    normalized = message.lower()
    keywords = (
        "market",
        "mandi",
        "price",
        "prices",
        "rate",
        "rates",
        "modal",
        "sell",
        "selling",
        "buyer",
        "commodity",
        "agmarknet",
        "bazaar",
        "bazar",
        "भाव",
        "कीमत",
        "मंडी",
        "दाम",
        "रेट",
    )
    return any(keyword in normalized for keyword in keywords)


async def build_tool_context(
    settings: Settings,
    user_id: str,
    req: AgentRequest,
    attachment: ChatAttachment | None,
) -> dict[str, object]:
    farms = await fetch_tool_json(settings.farm_service_url, "/farms", user_id)
    context: dict[str, object] = {"farms": farms}
    if should_preload_market_data(req.message):
        context["market_prices"] = await fetch_tool_json(
            settings.market_service_url, "/market/prices?limit=5", user_id
        )
        context["market_alerts"] = await fetch_tool_json(
            settings.market_service_url,
            "/market/alerts",
            user_id,
        )
    if req.account_name is not None and req.account_name.strip() != "":
        context["farmer_profile"] = {"name": req.account_name.strip()}
    farm_id = first_farm_id(farms)
    if farm_id is not None:
        context["primary_farm_weather"] = await fetch_tool_json(
            settings.farm_service_url,
            f"/farms/{farm_id}/weather",
            user_id,
        )
    if attachment is not None:
        context["attachment"] = {
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "size_bytes": attachment.size_bytes,
        }
        context["vision_detection"] = await detect_with_attachment(settings, user_id, attachment)
    if should_preload_crop_models(req.message):
        context["crop_models"] = await crop_model_bundle(settings, user_id)
    return context


def should_preload_crop_models(message: str) -> bool:
    lower = message.lower()
    return any(keyword in lower for keyword in ("crop", "yield", "fertil", "sow", "plant"))


def first_farm_id(farms: object) -> str | None:
    if not isinstance(farms, dict):
        return None
    data = farms.get("data")
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    if not isinstance(first, dict):
        return None
    farm_id = first.get("id")
    if isinstance(farm_id, str) and farm_id != "":
        return farm_id
    return None


async def stream_groq_tokens(
    settings: Settings,
    user_id: str,
    req: AgentRequest,
    attachment: ChatAttachment | None,
    recent_messages: list[ChatMessage],
) -> AsyncIterator[str]:
    tool_context = await build_tool_context(settings, user_id, req, attachment)
    model = ChatGroq(
        model=settings.groq_model,
        max_tokens=settings.groq_max_tokens,
        temperature=0.2,
        timeout=30,
        max_retries=0,
    )
    model_with_tools = model.bind_tools(agent_tool_specs())
    messages_for_model: list[SystemMessage | HumanMessage | AIMessage | ToolMessage] = [
        SystemMessage(content=build_system_prompt(req.language, tool_context)),
        HumanMessage(content=build_user_prompt(req, attachment, tool_context, recent_messages)),
    ]
    for _ in range(MAX_TOOL_ROUNDS):
        ai_message = await model_with_tools.ainvoke(messages_for_model)
        messages_for_model.append(ai_message)
        if not ai_message.tool_calls:
            break
        for tool_call in ai_message.tool_calls:
            result = await execute_agent_tool(
                settings, user_id, tool_call["name"], tool_call["args"], attachment
            )
            messages_for_model.append(
                ToolMessage(
                    content=trim_tool_result(result),
                    tool_call_id=cast(str, tool_call["id"]),
                )
            )
    final_messages: list[SystemMessage | HumanMessage | AIMessage | ToolMessage] = [
        *messages_for_model,
        HumanMessage(
            content=(
                "Give the final answer now. Be direct, use the tool facts, "
                "and do not mention tool mechanics."
            )
        ),
    ]
    async for chunk in model.astream(final_messages):
        content = cast(str | list[str | dict[str, object]], chunk.content)
        if isinstance(content, str) and content != "":
            yield content


def build_system_prompt(language: str, tool_context: dict[str, object]) -> str:
    relevant_titles = ", ".join(chunk.title for chunk in knowledge_chunks.values())
    knowledge = relevant_titles if relevant_titles else "No curated knowledge chunks are available."
    preferred_language = "Hindi" if language.lower().startswith("hi") else "English"
    return (
        "You are Khetibadi AI, an expert agricultural assistant for Indian farmers. "
        "Answer directly first. Do not start with sympathy or generic filler. Use short, "
        "decisive bullets when useful. You have tools for farmer farms, weather, market prices, "
        "crop recommendation, yield, fertilizer, and plant image disease detection. Call tools "
        "when a question needs current farmer data or prediction. If a required value is missing, "
        "ask one precise follow-up question. Do not invent unavailable facts. "
        f"Respond in {preferred_language}. Relevant knowledge titles: {knowledge}. "
        "A compact farmer context snapshot is included in the user message."
    )


def compact_tool_context(tool_context: dict[str, object]) -> dict[str, object]:
    compact: dict[str, object] = {}
    farmer_profile = tool_context.get("farmer_profile")
    if isinstance(farmer_profile, dict):
        compact["farmer_profile"] = compact_value(farmer_profile)
    farms = tool_context.get("farms")
    if isinstance(farms, dict):
        data = farms.get("data")
        if isinstance(data, list):
            compact["farms"] = [compact_farm(item) for item in data[:3] if isinstance(item, dict)]
    for key in ("primary_farm_weather", "attachment", "vision_detection"):
        value = tool_context.get(key)
        if value is not None:
            compact[key] = compact_value(value)
    market_prices = tool_context.get("market_prices")
    if isinstance(market_prices, dict):
        data = market_prices.get("data")
        if isinstance(data, list):
            compact["market_prices"] = [
                compact_market_price(item) for item in data[:3] if isinstance(item, dict)
            ]
    market_alerts = tool_context.get("market_alerts")
    if isinstance(market_alerts, dict):
        data = market_alerts.get("data")
        if isinstance(data, list):
            compact["market_alerts"] = data[:3]
    crop_models = tool_context.get("crop_models")
    if isinstance(crop_models, dict):
        info = crop_models.get("info")
        if isinstance(info, dict):
            compact["crop_model_mode"] = compact_value(info).get("model_mode")
    return compact


def compact_farm(item: dict[str, object]) -> dict[str, object]:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "crop": item.get("crop"),
        "soil_type": item.get("soil_type"),
        "area_hectares": item.get("area_hectares"),
    }


def compact_market_price(item: dict[str, object]) -> dict[str, object]:
    return {
        "commodity": item.get("commodity"),
        "state": item.get("state"),
        "market": item.get("market"),
        "modal_price": item.get("modal_price"),
        "unit": item.get("unit"),
        "observed_at": item.get("observed_at"),
    }


def compact_value(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {"value": value}
    blocked = {"annotated_image_base64", "raw", "boundary"}
    return {key: item for key, item in value.items() if key not in blocked}


def agent_tool_specs() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_farms",
                "description": (
                    "Fetch the authenticated farmer's farms, boundaries, soil type, crop, and area."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_farm_weather",
                "description": "Fetch current OpenWeatherMap weather for one farm by farm ID.",
                "parameters": {
                    "type": "object",
                    "properties": {"farm_id": {"type": "string"}},
                    "required": ["farm_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_soil_samples",
                "description": "Fetch soil samples for one farm by farm ID.",
                "parameters": {
                    "type": "object",
                    "properties": {"farm_id": {"type": "string"}},
                    "required": ["farm_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_market_prices",
                "description": (
                    "Fetch latest mandi prices, optionally filtered by commodity or state."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commodity": {"type": "string"},
                        "state": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_market_alerts",
                "description": "Fetch the authenticated farmer's price alerts.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recommend_crop",
                "description": (
                    "Run the crop recommendation model for soil nutrients and weather features."
                ),
                "parameters": crop_feature_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "predict_yield",
                "description": "Run the yield model for a crop and area.",
                "parameters": yield_feature_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recommend_fertilizer",
                "description": (
                    "Run the fertilizer recommendation model for soil and crop conditions."
                ),
                "parameters": fertilizer_feature_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "detect_plant_disease",
                "description": (
                    "Use the attached crop image with the plant disease model. "
                    "Requires an uploaded image."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


def crop_feature_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "nitrogen": {"type": "number"},
            "phosphorus": {"type": "number"},
            "potassium": {"type": "number"},
            "temperature": {"type": "number"},
            "humidity": {"type": "number"},
            "ph": {"type": "number"},
            "rainfall": {"type": "number"},
            "season": {"type": "string"},
            "state": {"type": "string"},
        },
        "required": [
            "nitrogen",
            "phosphorus",
            "potassium",
            "temperature",
            "humidity",
            "ph",
            "rainfall",
        ],
    }


def yield_feature_schema() -> dict[str, object]:
    schema = crop_feature_schema()
    properties = cast(dict[str, object], schema["properties"])
    properties.update(
        {
            "crop": {"type": "string"},
            "area_hectares": {"type": "number"},
            "district": {"type": "string"},
        }
    )
    schema["required"] = [*cast(list[str], schema["required"]), "crop", "area_hectares"]
    return schema


def fertilizer_feature_schema() -> dict[str, object]:
    schema = crop_feature_schema()
    properties = cast(dict[str, object], schema["properties"])
    properties.update(
        {
            "crop": {"type": "string"},
            "soil_type": {"type": "string"},
            "moisture": {"type": "number"},
        }
    )
    schema["required"] = [*cast(list[str], schema["required"]), "crop", "soil_type"]
    return schema


async def execute_agent_tool(
    settings: Settings,
    user_id: str,
    name: str,
    args: dict[str, object],
    attachment: ChatAttachment | None,
) -> str:
    if name == "get_farms":
        return json.dumps(
            await fetch_tool_json(settings.farm_service_url, "/farms", user_id), default=str
        )
    if name == "get_farm_weather":
        farm_id = str(args.get("farm_id", "")).strip()
        if farm_id == "":
            return json.dumps({"error": "farm_id_required"})
        return json.dumps(
            await fetch_tool_json(settings.farm_service_url, f"/farms/{farm_id}/weather", user_id),
            default=str,
        )
    if name == "get_soil_samples":
        farm_id = str(args.get("farm_id", "")).strip()
        if farm_id == "":
            return json.dumps({"error": "farm_id_required"})
        return json.dumps(
            await fetch_tool_json(
                settings.farm_service_url,
                f"/farms/{farm_id}/soil-samples",
                user_id,
            ),
            default=str,
        )
    if name == "get_market_prices":
        return json.dumps(await fetch_market_prices(settings, user_id, args), default=str)
    if name == "get_market_alerts":
        return json.dumps(
            await fetch_tool_json(settings.market_service_url, "/market/alerts", user_id),
            default=str,
        )
    if name == "recommend_crop":
        return json.dumps(
            await post_tool_json(settings.ml_crop_service_url, "/ml/crop/recommend", user_id, args),
            default=str,
        )
    if name == "predict_yield":
        return json.dumps(
            await post_tool_json(settings.ml_crop_service_url, "/ml/crop/yield", user_id, args),
            default=str,
        )
    if name == "recommend_fertilizer":
        return json.dumps(
            await post_tool_json(
                settings.ml_crop_service_url, "/ml/crop/fertilizer", user_id, args
            ),
            default=str,
        )
    if name == "detect_plant_disease":
        return json.dumps(await detect_with_attachment(settings, user_id, attachment), default=str)
    return json.dumps({"error": "unknown_tool", "tool": name})


async def fetch_market_prices(settings: Settings, user_id: str, args: dict[str, object]) -> object:
    params: list[str] = []
    for key in ("commodity", "state", "limit"):
        value = args.get(key)
        if value is not None and str(value).strip() != "":
            params.append(f"{key}={str(value).strip()}")
    query = "&".join(params)
    path = "/market/prices" if query == "" else f"/market/prices?{query}"
    return await fetch_tool_json(settings.market_service_url, path, user_id)


async def crop_model_bundle(settings: Settings, user_id: str) -> dict[str, object]:
    return {
        "info": await fetch_tool_json(settings.ml_crop_service_url, "/ml/crop/info", user_id),
        "feature_importance": await fetch_tool_json(
            settings.ml_crop_service_url,
            "/ml/crop/feature-importance",
            user_id,
        ),
    }


async def fetch_tool_json(base_url: str, path: str, user_id: str) -> object:
    headers = signed_headers(user_id)
    try:
        async with httpx.AsyncClient(timeout=CONTEXT_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{base_url.rstrip('/')}{path}", headers=headers)
        return parse_tool_response(response)
    except Exception as exc:
        logger.warning("tool fetch failed", path=path, error=str(exc))
        return {"error": "tool_unavailable", "path": path}


async def post_tool_json(
    base_url: str, path: str, user_id: str, payload: dict[str, object]
) -> object:
    headers = {**signed_headers(user_id), "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=CONTEXT_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}{path}", headers=headers, json=payload
            )
        return parse_tool_response(response)
    except Exception as exc:
        logger.warning("tool post failed", path=path, error=str(exc))
        return {"error": "tool_unavailable", "path": path}


async def detect_with_attachment(
    settings: Settings,
    user_id: str,
    attachment: ChatAttachment | None,
) -> object:
    if attachment is None:
        return {"error": "image_required"}
    headers = signed_headers(user_id)
    files = {"image": (attachment.filename, attachment.data, attachment.content_type)}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.ml_vision_service_url.rstrip('/')}/ml/vision/detect",
                headers=headers,
                files=files,
            )
        return parse_tool_response(response)
    except Exception as exc:
        logger.warning("vision tool failed", error=str(exc))
        return {"error": "vision_tool_unavailable"}


def parse_tool_response(response: httpx.Response) -> object:
    try:
        payload = response.json()
    except ValueError:
        payload = {"body": response.text[:1000]}
    if response.is_success:
        return payload
    return {"error": "tool_http_error", "status": response.status_code, "payload": payload}


def signed_headers(user_id: str) -> dict[str, str]:
    settings = get_settings()
    timestamp = int(time.time())
    signature = hmac.new(
        settings.hmac_secret.encode(),
        f"{user_id}:{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-User-ID": user_id,
        "X-Timestamp": str(timestamp),
        "X-HMAC-Signature": signature,
    }


def trim_tool_result(value: str) -> str:
    if len(value) <= MAX_TOOL_RESULT_CHARS:
        return value
    return f"{value[:MAX_TOOL_RESULT_CHARS]}..."


async def save_session(session: ChatSession) -> None:
    sessions[session.id] = session
    messages.setdefault(session.id, [])
    if db_pool is None:
        return
    async with db_pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO chat_sessions (
                id, user_id, title, channel, external_thread_id, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                channel = EXCLUDED.channel,
                external_thread_id = EXCLUDED.external_thread_id,
                updated_at = EXCLUDED.updated_at
            """,
            (
                session.id,
                session.user_id,
                session.title,
                session.channel,
                session.external_thread_id,
                session.created_at,
                session.updated_at,
            ),
        )


async def find_sessions(user_id: str) -> list[ChatSession]:
    if db_pool is None:
        visible = [session for session in sessions.values() if session.user_id == user_id]
        visible.sort(key=lambda session: session.updated_at, reverse=True)
        return visible
    async with db_pool.connection() as conn:
        rows = await conn.execute(
            """
            SELECT id::text, user_id, title, channel, external_thread_id, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = %s
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )
        return [session_from_row(cast(dict[str, object], row)) async for row in rows]


async def remove_session(session_id: str) -> None:
    sessions.pop(session_id, None)
    messages.pop(session_id, None)
    if db_pool is None:
        return
    async with db_pool.connection() as conn:
        await conn.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))


async def update_session_timestamp(session_id: str, updated_at: datetime) -> None:
    session = sessions.get(session_id)
    if session is not None:
        session.updated_at = updated_at
    if db_pool is None:
        return
    async with db_pool.connection() as conn:
        await conn.execute(
            "UPDATE chat_sessions SET updated_at = %s WHERE id = %s",
            (updated_at, session_id),
        )


async def save_message(message: ChatMessage) -> None:
    messages.setdefault(message.session_id, []).append(message)
    if db_pool is None:
        return
    async with db_pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO chat_messages (
                id, session_id, user_id, channel, role, content, status, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                message.id,
                message.session_id,
                message.user_id,
                message.channel,
                message.role,
                message.content,
                message.status,
                message.created_at,
            ),
        )


async def find_messages(session_id: str) -> list[ChatMessage]:
    if db_pool is None:
        return messages.get(session_id, [])
    async with db_pool.connection() as conn:
        rows = await conn.execute(
            """
            SELECT id::text, session_id::text, user_id, channel, role, content, status, created_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        return [message_from_row(cast(dict[str, object], row)) async for row in rows]


async def recent_chat_history(session_id: str, exclude_message_id: str) -> list[ChatMessage]:
    history = [
        message for message in await find_messages(session_id) if message.id != exclude_message_id
    ]
    return history[-MAX_RECENT_CHAT_MESSAGES:]


async def save_knowledge(chunk: KnowledgeChunk) -> None:
    knowledge_chunks[chunk.id] = chunk
    if db_pool is None:
        return
    async with db_pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO knowledge_chunks (id, title, content, source, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                source = EXCLUDED.source
            """,
            (chunk.id, chunk.title, chunk.content, chunk.source, chunk.created_at),
        )


async def get_owned_session(session_id: str, user_id: str) -> ChatSession:
    session = await find_session(session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "chat session not found"},
        )
    return session


async def find_session(session_id: str) -> ChatSession | None:
    if db_pool is None:
        return sessions.get(session_id)
    async with db_pool.connection() as conn:
        row = await conn.execute(
            """
            SELECT id::text, user_id, title, channel, external_thread_id, created_at, updated_at
            FROM chat_sessions
            WHERE id = %s
            """,
            (session_id,),
        )
        item = await row.fetchone()
    if item is None:
        return None
    return session_from_row(cast(dict[str, object], item))


async def find_or_create_bridge_session(user_id: str, req: BridgeMessageRequest) -> ChatSession:
    existing = await find_bridge_session(user_id, req.channel, req.external_thread_id)
    if existing is not None:
        return existing
    now = datetime.now(UTC)
    session = ChatSession(
        id=str(uuid4()),
        user_id=user_id,
        title=req.title.strip(),
        channel=req.channel,
        external_thread_id=req.external_thread_id,
        created_at=now,
        updated_at=now,
    )
    await save_session(session)
    return session


async def find_bridge_session(
    user_id: str,
    channel: ChatChannel,
    external_thread_id: str,
) -> ChatSession | None:
    if db_pool is None:
        for session in sessions.values():
            if (
                session.user_id == user_id
                and session.channel == channel
                and session.external_thread_id == external_thread_id
            ):
                return session
        return None
    async with db_pool.connection() as conn:
        row = await conn.execute(
            """
            SELECT id::text, user_id, title, channel, external_thread_id, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = %s AND channel = %s AND external_thread_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id, channel, external_thread_id),
        )
        item = await row.fetchone()
    if item is None:
        return None
    return session_from_row(cast(dict[str, object], item))


def session_from_row(row: dict[str, object]) -> ChatSession:
    return ChatSession.model_validate(row)


def message_from_row(row: dict[str, object]) -> ChatMessage:
    return ChatMessage.model_validate(row)


async def enforce_rate_limit(user_id: str) -> None:
    settings = get_settings()
    if redis_client is not None:
        now_score = time.time()
        key = f"chat:ratelimit:{user_id}"
        window_start = now_score - RATE_WINDOW_SECONDS
        await redis_client.zremrangebyscore(key, 0, window_start)
        await redis_client.zadd(key, {str(uuid4()): now_score})
        await redis_client.expire(key, RATE_WINDOW_SECONDS)
        count = await redis_client.zcard(key)
        if count > settings.chat_rate_limit_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"error": "rate_limited", "message": "chat rate limit exceeded"},
                headers={"Retry-After": str(RATE_WINDOW_SECONDS)},
            )
        return
    now = datetime.now(UTC)
    window_start_dt = now - timedelta(seconds=RATE_WINDOW_SECONDS)
    recent = [seen_at for seen_at in rate_limits.get(user_id, []) if seen_at >= window_start_dt]
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
