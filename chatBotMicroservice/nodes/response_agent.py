import time
from langchain_core.messages import SystemMessage, HumanMessage
from state import AgentState
from models import llm_respond
from nodes.helpers import (
    log, _sla_exceeded, _llm_text, _truncate,
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
    pm_plan = state.get("pm_plan", "")
    tool_context = _extract_tool_context(state["messages"])
    display_results = state.get("display_results", [])
    data_fetched = state.get("data_fetched", True)

    log.info(
        f"[RESPOND] Inputs — pm_plan: {bool(pm_plan)}, "
        f"tool_context: {len(tool_context)} chars, "
        f"display_results: {len(display_results)}, "
        f"data_fetched: {data_fetched}"
    )

    # ── Short-circuit if data was required but nothing came back ──────────────
    data_needed_match = DATA_NEEDED_EXTRACT.search(pm_plan)
    data_needed = data_needed_match.group(1).strip() if data_needed_match else ""
    needs_data = data_needed.lower() not in ("none", "n/a", "")

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

    chart_note = (
        "A chart has already been rendered in the UI. Reference it naturally but do NOT describe it."
        if display_results else
        "No chart was rendered."
    )

    is_simple = len(user_msg.split()) <= 15

    system_parts = [
        RESPONSE_AGENT_BASE_PROMPT,
        chart_note,
        (
            "Keep your response short and natural — match the brevity of the user's message."
            if is_simple else
            "Write in natural prose. Be thorough but concise."
        ),
    ]
    if tool_context:
        system_parts.append(f"\nResearch context:\n{tool_context[:RESPOND_TOOL_CONTEXT_WINDOW]}")

    # Always attach the PM plan — without it, short queries give the model zero
    # context about what was researched, causing empty/nonsense LLM output.
    user_turn = user_msg
    if pm_plan:
        user_turn += f"\n\n[Execution plan for context]:\n{pm_plan[:RESPOND_PM_PLAN_WINDOW]}"

    log.info(
        f"[RESPOND] Calling llm_respond — "
        f"{len(chr(10).join(system_parts))} char system, {len(user_turn)} char user turn"
    )

    content = ""
    response = None
    try:
        response = llm_respond.invoke([
            SystemMessage(content="\n".join(system_parts)),
            HumanMessage(content=user_turn),
        ])
        content = _llm_text(response).strip()
        log.info(
            f"[RESPOND] LLM returned {len(content)} chars "
            f"in {time.time()-t0:.2f}s: {_truncate(content)}"
        )
    except Exception as e:
        log.error(f"[RESPOND] LLM failed: {e}", exc_info=True)
        content = "I wasn't able to generate a response. Please try again."

    # Catch model non-answers (e.g. llama3.2 returning "No output generated."
    # when it has no context to work with).
    if not content or content.lower().startswith("no output generated"):
        log.warning(f"[RESPOND] Model returned empty/invalid output: {repr(content)}")
        content = "I wasn't able to generate a response. Please try again."

    extra_chunks = []
    if display_results:
        flat = []
        for r in display_results:
            flat.extend(r) if isinstance(r, list) else flat.append(r)
        extra_chunks.append(emit("display_modules", flat))
        log.info(f"[RESPOND] Emitting display_modules with {len(flat)} item(s)")

    stream_chunks = extra_chunks + [emit("response_content", content)]
    log.info(f"[RESPOND] ✓ Done in {time.time() - t0:.2f}s | {len(stream_chunks)} chunk(s)")

    return {
        "messages": [response] if response else [],
        "stream_chunks": stream_chunks,
    }
