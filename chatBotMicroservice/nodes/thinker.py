import queue
import time
from langchain_core.messages import SystemMessage, HumanMessage
from state import AgentState
from models import llm_fast
from nodes.helpers import log, _sla_exceeded, _llm_text, emit
from nodes.prompts import THINKER_PROMPT


def thinker_node(state: AgentState) -> AgentState:
    log.info("━━━ [NODE 2A / THINKER] Narrating plan to frontend")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[THINKER] Skipping — SLA exceeded")
        return {"messages": [], "stream_chunks": []}

    pm_plan = state.get("pm_plan", "")
    token_queue: queue.Queue = state.get("token_queue")
    retry_count = state.get("retry_count", 0)

    log.info(
        f"[THINKER] pm_plan present: {bool(pm_plan)} | "
        f"token_queue: {token_queue is not None} | "
        f"retry_count: {retry_count}"
    )

    # On retry runs the user already saw the initial thinking — skip re-emission
    # to prevent duplicate thinking_content appearing in the stream.
    if retry_count > 0:
        log.info("[THINKER] Retry run — suppressing thinking re-emission")
        if token_queue:
            token_queue.put("__thinking_done__")
        return {"messages": [], "stream_chunks": []}

    if not pm_plan:
        log.warning("[THINKER] No PM plan available — skipping")
        if token_queue:
            token_queue.put("__thinking_done__")
        return {"messages": [], "stream_chunks": []}

    thinking_chunks = []

    try:
        log.info("[THINKER] Invoking llm_fast")
        response = llm_fast.invoke([
            SystemMessage(content=THINKER_PROMPT),
            HumanMessage(content=f"Plan:\n{pm_plan}"),
        ])

        think_text = _llm_text(response).strip()
        if not think_text:
            raise ValueError("Empty thinker output")

        chunk_str = emit("thinking_content", think_text)
        thinking_chunks.append(chunk_str)
        if token_queue:
            token_queue.put(chunk_str)
        log.info(f"[THINKER] Generated {len(think_text)} chars")

    except Exception as e:
        log.error(f"[THINKER] Failed: {e}", exc_info=True)
        fallback = "Let me work through this step by step based on what you've asked..."
        chunk_str = emit("thinking_content", fallback)
        thinking_chunks.append(chunk_str)
        if token_queue:
            token_queue.put(chunk_str)
        log.warning("[THINKER] Emitted fallback thinking token")

    if token_queue:
        token_queue.put("__thinking_done__")
        log.info("[THINKER] __thinking_done__ sent")

    log.info(f"[THINKER] ✓ Done in {time.time() - t0:.2f}s | {len(thinking_chunks)} chunk(s)")
    return {"messages": [], "stream_chunks": thinking_chunks}
