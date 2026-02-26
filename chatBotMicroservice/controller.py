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
from nodes.helpers import LOG_CHUNK_PREVIEW, emit

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
        # ── Two separate queues ───────────────────────────────────────────────
        # thinking_queue: real-time status updates streamed as they happen
        # result_queue:   final response/display chunks flushed after graph ends
        thinking_queue: queue.Queue = queue.Queue()
        result_queue:   queue.Queue = queue.Queue()

        initial_state: AgentState = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ],
            "stream_chunks":        [],
            "display_results":      [],
            "data_fetched":         False,
            "evaluation":           "",
            "evaluation_critique":  "",
            "retry_count":          0,
            "token_queue":          thinking_queue,   # nodes write status here
            "start_time":           time.time(),
        }

        def run_graph():
            node_chunks: dict[str, list[str]] = {}
            try:
                for event in agent_graph.stream(initial_state, stream_mode="updates"):
                    for node_name, node_state in event.items():
                        chunks = node_state.get("stream_chunks", [])
                        if chunks:
                            log.info(f"[STREAM] {len(chunks)} chunk(s) from '{node_name}'")

                        # Separate thinking vs final content
                        for chunk in chunks:
                            try:
                                chunk_type = json.loads(chunk).get("type", "")
                            except Exception:
                                chunk_type = ""

                            if chunk_type == "thinking_content":
                                # Real-time — push straight to thinking queue
                                thinking_queue.put(chunk)
                            else:
                                # Final content — collect for ordered flush
                                node_chunks.setdefault(node_name, []).append(chunk)

                        # Build display chunk if display agent ran
                        if node_name == "display_agent":
                            display_results = node_state.get("display_results", [])
                            if display_results:
                                flat = []
                                for r in display_results:
                                    flat.extend(r) if isinstance(r, list) else flat.append(r)
                                display_chunk = emit("display_modules", flat)
                                node_chunks.setdefault("display_agent_emit", []).append(display_chunk)
                                log.info(f"[STREAM] display_modules emitted with {len(flat)} item(s)")

            except Exception as e:
                log.error(f"[GRAPH] Error during graph execution: {e}", exc_info=True)
                node_chunks["__error__"] = [
                    json.dumps({
                        "type": "response_content",
                        "data": "Something went wrong. Please try again.",
                    }) + "\n"
                ]
            finally:
                # Collect and order final chunks, then signal done
                TYPE_ORDER = {"response_content": 0, "display_modules": 1}
                all_final = [c for chunks in node_chunks.values() for c in chunks]
                all_final.sort(
                    key=lambda c: TYPE_ORDER.get(
                        json.loads(c).get("type", "") if c.strip() else "", 99
                    )
                )
                for chunk in all_final:
                    result_queue.put(chunk)

                result_queue.put("__graph_done__")
                thinking_queue.put("__graph_done__")  # unblocks thinking consumer too

        thread = threading.Thread(target=run_graph, daemon=True)
        thread.start()

        loop = asyncio.get_event_loop()

        # ── Stream thinking in real-time until graph finishes ─────────────────
        # We poll thinking_queue continuously. Once we see __graph_done__ there
        # we know the graph is finished and result_queue is fully populated.
        while True:
            item = await loop.run_in_executor(None, thinking_queue.get)

            if item == "__graph_done__":
                log.info("[CONTROLLER] Graph done signal received on thinking queue")
                break

            if item == "__thinking_done__":
                # Emitted by stream_status after each individual status message —
                # safe to ignore here since we're draining continuously anyway
                continue

            log.info(f"[CONTROLLER] Thinking: {item[:LOG_CHUNK_PREVIEW].strip()}")
            yield item

        # ── Join thread then flush final results ──────────────────────────────
        await loop.run_in_executor(None, thread.join)
        log.info("[CONTROLLER] Thread joined — flushing final chunks")

        while True:
            item = await loop.run_in_executor(None, result_queue.get)
            if item == "__graph_done__":
                break
            log.info(f"[CONTROLLER] Flushing: {item[:LOG_CHUNK_PREVIEW].strip()}")
            yield item

    return StreamingResponse(generate(), media_type="text/plain")