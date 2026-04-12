"""ml-crop — FastAPI application entry point."""
from fastapi import FastAPI

app = FastAPI(title="khetibadi-ml-crop")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
