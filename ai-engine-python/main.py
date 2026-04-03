from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from core.events import to_ndjson_line
from core.schemas import InternalReviewRunRequest
from core.state_graph import run_review_state_graph

app = FastAPI(title="Sentinel-CR AI Engine Python", version="0.7.0-day7")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "UP",
        "service": "ai-engine-python",
    }


@app.post("/internal/reviews/run")
async def run_review(request: InternalReviewRunRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async for event in run_review_state_graph(request):
            yield to_ndjson_line(event)

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
