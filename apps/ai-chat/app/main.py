"""ai-chat — FastAPI application entry point."""
from fastapi import FastAPI

app = FastAPI(title="khetibadi-ai-chat")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
