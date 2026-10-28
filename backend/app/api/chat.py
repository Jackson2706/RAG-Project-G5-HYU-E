"""Chat endpoints (blocking and SSE streaming) and trace lookup."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import State
from app.models.config import ResolvedConfig
from app.models.pipeline import ChatRequest, ChatResponse, ExecutionTrace, PipelineEvent
from app.rag.registry import ONLINE_ORDER, resolve_config

router = APIRouter(tags=["chat"])


def _resolve(body: ChatRequest) -> ResolvedConfig:
    result = resolve_config(body.config, ONLINE_ORDER)
    if not result.valid:
        raise HTTPException(422, {"message": "Invalid pipeline configuration", "errors": [e.model_dump() for e in result.errors]})
    return result.resolved  # type: ignore[return-value]


@router.post("/chat", response_model=ChatResponse, summary="Run the pipeline and return the answer with its full trace")
async def chat(body: ChatRequest, state: State) -> ChatResponse:
    config = _resolve(body)
    trace = await state.pipeline.run(body.question.strip(), config, body.session_id)
    return ChatResponse(request_id=trace.request_id, result=trace.result, trace=trace)


def _sse(event: PipelineEvent) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json(exclude_none=True)}\n\n"


@router.post("/chat/stream", summary="Run the pipeline, streaming stage events and answer tokens as Server-Sent Events",
             response_class=StreamingResponse)  # fmt: skip
async def chat_stream(body: ChatRequest, request: Request, state: State) -> StreamingResponse:
    config = _resolve(body)  # validation errors are returned as normal 422 responses before streaming starts
    queue: asyncio.Queue[PipelineEvent | None] = asyncio.Queue()

    async def run() -> None:
        try:
            await state.pipeline.run(body.question.strip(), config, body.session_id, emit=queue.put)
        finally:
            await queue.put(None)

    async def events() -> AsyncIterator[str]:
        task = asyncio.create_task(run())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10)
                except TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": keep-alive\n\n"
                    continue
                if event is None:
                    break
                yield _sse(event)
        finally:
            if not task.done():
                task.cancel()  # client went away: stop retrieval/generation (the trace is saved as cancelled)
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/traces/{request_id}", response_model=ExecutionTrace, summary="Stored execution trace of one request")
async def get_trace(request_id: str, state: State) -> ExecutionTrace:
    if not request_id.isalnum() or len(request_id) > 64:
        raise HTTPException(400, "Invalid request ID")
    trace = await asyncio.to_thread(state.services.mongo.get_trace, request_id)
    if trace is None:
        raise HTTPException(404, "Trace not found")
    return trace
