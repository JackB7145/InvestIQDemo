import time
from langchain_core.messages import SystemMessage, HumanMessage
from state import AgentState
from models import llm_respond
from nodes.helpers import (
    log, _sla_exceeded, _truncate, llm_call,
    DATA_NEEDED_EXTRACT,
    RESPOND_TOOL_CONTEXT_WINDOW,
    RESPOND_PM_PLAN_WINDOW,
    _extract_tool_context,
    emit,
)
from nodes.prompts import RESPONSE_AGENT_BASE_PROMPT


def response_agent_node(state: AgentState) -> AgentState:
    log.info("━━━ [NODE 4 / RESPONSE AGENT] Generating final answer")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[RESPOND] SLA exceeded — returning fallback")
        return {
            "messages": [],
            "stream_chunks": [emit(
                "response_content",
                "I wasn't able to complete your request in time. Please try again."
            )],
        }

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )
    pm_plan     = state.get("pm_plan", "")
    tool_context = _extract_tool_context(state["messages"])
    data_fetched = state.get("data_fetched", True)

    log.info(
        f"[RESPOND] Inputs — pm_plan: {bool(pm_plan)}, "
        f"tool_context: {len(tool_context)} chars, "
        f"data_fetched: {data_fetched}"
    )

    # ── Short-circuit if data was required but nothing came back ──────────────
    data_needed_match = DATA_NEEDED_EXTRACT.search(pm_plan)
    data_needed  = data_needed_match.group(1).strip() if data_needed_match else ""
    needs_data   = data_needed.lower() not in ("none", "n/a", "")

    if needs_data and not data_fetched:
        log.warning("[RESPOND] Data was required but not fetched — returning honest failure")
        content = (
            "I wasn't able to retrieve the data needed to answer this accurately. "
            "This could be due to an API limit or connection issue. Please try again in a moment."
        )
        return {
            "messages": [],
            "stream_chunks": [emit("response_content", content)],
        }

    # ── Build system prompt ───────────────────────────────────────────────────
    is_simple = len(user_msg.split()) <= 15

    system_parts = [
        RESPONSE_AGENT_BASE_PROMPT,
        "Do not mention charts or visualizations in your response.",
        (
            "Keep your response short and natural — match the brevity of the user's message."
            if is_simple else
            "Write in natural prose. Be thorough but concise."
        ),
    ]
    if tool_context:
        system_parts.append(f"\nResearch context:\n{tool_context[:RESPOND_TOOL_CONTEXT_WINDOW]}")

    user_turn = user_msg
    if pm_plan:
        user_turn += f"\n\n[Execution plan for context]:\n{pm_plan[:RESPOND_PM_PLAN_WINDOW]}"

    log.info(
        f"[RESPOND] Calling llm_respond — "
        f"{len(chr(10).join(system_parts))} char system, {len(user_turn)} char user turn"
    )

    # ── LLM call via intermediary ─────────────────────────────────────────────
    content = llm_call(
        state,
        llm_respond.invoke,
        [
            SystemMessage(content="\n".join(system_parts)),
            HumanMessage(content=user_turn),
        ],
        status_before="✍️ Generating response…",
        status_after="✅ Response complete",
        label="RESPOND",
    ).strip()

    if not content or content.lower().startswith("no output generated"):
        log.warning(f"[RESPOND] Model returned empty/invalid output: {repr(content)}")
        content = "I wasn't able to generate a response. Please try again."

    stream_chunks = [emit("response_content", content)]
    log.info(f"[RESPOND] ✓ Done in {time.time() - t0:.2f}s | {len(stream_chunks)} chunk(s)")

    return {
        "messages": [],
        "stream_chunks": stream_chunks,
    }