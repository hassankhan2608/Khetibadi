"""ml-vision — FastAPI application entry point."""
from fastapi import FastAPI

app = FastAPI(title="khetibadi-ml-vision")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
