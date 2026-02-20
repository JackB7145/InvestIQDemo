import json
import queue
import threading
import time
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from graph import agent_graph
from state import AgentState

log = logging.getLogger("agent")

router = APIRouter()

SYSTEM_PROMPT = (
    "You are a helpful data analyst assistant. "
    "You have access to tools and should use them when appropriate. "
    "Be concise and precise in your responses."
)


class ChatRequest(BaseModel):
    prompt: str


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/chat")
def chat(req: ChatRequest):
    if not req.prompt.strip():
        return {"error": "Prompt is required"}, 400

    def generate():
        token_queue: queue.Queue = queue.Queue()
        final_chunks: list[str] = []

        def run_graph():
            initial_state: AgentState = {
                "messages": [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=req.prompt),
                ],
                "stream_chunks": [],
                "display_results": [],
                "reasoning_summary": "",
                "evaluation": "",
                "retry_count": 0,
                "token_queue": token_queue,
                "start_time": time.time(),  # SLA clock starts here
                "needs_validation": False,  # flip to True for high-stakes queries
            }

            try:
                # stream_mode="updates" yields state delta per node as it completes
                for event in agent_graph.stream(initial_state, stream_mode="updates"):
                    for node_name, node_state in event.items():
                        chunks = node_state.get("stream_chunks", [])
                        if chunks:
                            log.info(f"[STREAM] {len(chunks)} chunk(s) from '{node_name}'")
                        for chunk in chunks:
                            final_chunks.append(chunk)
            except Exception as e:
                log.error(f"[GRAPH] Error during graph execution: {e}")
                final_chunks.append(
                    json.dumps({"type": "response_content", "data": "Something went wrong. Please try again."}) + "\n"
                )
            finally:
                token_queue.put("__graph_done__")

        # Run graph in background so we can stream thinking tokens live
        thread = threading.Thread(target=run_graph, daemon=True)
        thread.start()

        # Drain token queue — yields thinking tokens to frontend as they arrive
        while True:
            item = token_queue.get()

            if item == "__thinking_done__":
                log.info("[CONTROLLER] Thinking stream complete")
                continue

            if item == "__graph_done__":
                log.info("[CONTROLLER] Graph complete — flushing remaining chunks")
                break

            # Live thinking token — yield immediately
            yield item

        # Graph done — yield response_content and display_modules in correct order
        TYPE_ORDER = {"thinking_content": 0, "response_content": 1, "display_modules": 2}
        final_chunks.sort(
            key=lambda c: TYPE_ORDER.get(json.loads(c).get("type", ""), 99)
        )
        for chunk in final_chunks:
            yield chunk

        thread.join()

    return StreamingResponse(generate(), media_type="text/plain")