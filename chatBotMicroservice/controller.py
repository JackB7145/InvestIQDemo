import asyncio
import json
import queue
import threading
import time
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from graph import agent_graph
from state import AgentState
from nodes.helpers import LOG_CHUNK_PREVIEW

log = logging.getLogger("agent")
router = APIRouter()

SYSTEM_PROMPT = (
    "You are a helpful data analyst assistant. "
    "You have access to tools and should use them when appropriate. "
    "Be concise and precise in your responses."
)

MAX_PROMPT_LENGTH = 2000


class ChatRequest(BaseModel):
    prompt: str


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/chat")
async def chat(req: ChatRequest):
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Prompt too long. Maximum is {MAX_PROMPT_LENGTH} characters.",
        )

    async def generate():
        token_queue: queue.Queue = queue.Queue()
        final_chunks: list[str] = []

        initial_state: AgentState = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ],
            "stream_chunks": [],
            "display_results": [],
            "data_fetched": False,
            "evaluation": "",
            "evaluation_critique": "",
            "retry_count": 0,
            "token_queue": token_queue,
            "start_time": time.time(),
        }

        def run_graph():
            # Keyed by node name so retry runs replace (not accumulate) earlier chunks.
            node_chunks: dict[str, list[str]] = {}
            try:
                for event in agent_graph.stream(initial_state, stream_mode="updates"):
                    for node_name, node_state in event.items():
                        chunks = node_state.get("stream_chunks", [])
                        if chunks:
                            log.info(f"[STREAM] {len(chunks)} chunk(s) from '{node_name}'")
                        non_thinking: list[str] = []
                        for chunk in chunks:
                            try:
                                chunk_type = json.loads(chunk).get("type", "")
                            except Exception:
                                chunk_type = ""
                            # thinking already streamed live via token_queue
                            if chunk_type != "thinking_content":
                                non_thinking.append(chunk)
                        # Replace previous chunks from this node (handles retries)
                        node_chunks[node_name] = non_thinking
            except Exception as e:
                log.error(f"[GRAPH] Error during graph execution: {e}", exc_info=True)
                final_chunks.append(
                    json.dumps({
                        "type": "response_content",
                        "data": "Something went wrong. Please try again.",
                    }) + "\n"
                )
            finally:
                # Flatten per-node chunks into final_chunks (retry runs already replaced)
                for chunks in node_chunks.values():
                    final_chunks.extend(chunks)
                # Always signal completion — consumers unblock regardless of success/error
                token_queue.put("__graph_done__")

        # Run sync graph in a daemon thread; use asyncio to non-blockingly drain the queue
        thread = threading.Thread(target=run_graph, daemon=True)
        thread.start()

        loop = asyncio.get_event_loop()

        # Yield live thinking tokens as they arrive; stop on graph completion signal
        while True:
            item = await loop.run_in_executor(None, token_queue.get)
            if item == "__graph_done__":
                log.info("[CONTROLLER] Graph complete — flushing remaining chunks")
                break
            if item == "__thinking_done__":
                log.info("[CONTROLLER] Thinking stream complete")
                continue
            yield item

        # Graph is confirmed done — yield display_modules first, then response_content
        TYPE_ORDER = {"display_modules": 0, "response_content": 1}
        final_chunks.sort(
            key=lambda c: TYPE_ORDER.get(
                json.loads(c).get("type", "") if c.strip() else "", 99
            )
        )
        for chunk in final_chunks:
            log.info(f"[CONTROLLER] Flushing: {chunk[:LOG_CHUNK_PREVIEW].strip()}")
            yield chunk

        # Daemon thread cleans up automatically — no thread.join() needed

    return StreamingResponse(generate(), media_type="text/plain")
