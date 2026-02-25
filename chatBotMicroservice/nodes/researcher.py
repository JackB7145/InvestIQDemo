import json
import time
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from state import AgentState
from models import llm_medium
from tools import TOOL_MAP
from nodes.helpers import (
    log, _sla_exceeded, _llm_text, _truncate,
    DATA_NEEDED_EXTRACT,
    MAX_PROMPT_CHARS,
    RESEARCHER_MAX_ITERATIONS,
    RESEARCHER_QUESTION_WINDOW,
    RESEARCHER_NEED_WINDOW,
    RESEARCHER_CONTEXT_WINDOW,
)
from nodes.prompts import RESEARCHER_PLANNER_PROMPT


def _is_tool_result_an_error(result: str) -> bool:
    error_markers = [
        "Error Message",
        "Note: Thank you for using Alpha Vantage",
        "Information:",
        "No Wikipedia article found",
        "not found or empty",
        "No content found",
        "Error retrieving context",
        "rate limit",
        "timed out",
        "Unexpected error",
        "Network error",
    ]
    return any(m.lower() in result.lower() for m in error_markers)


def researcher_node(state: AgentState) -> AgentState:
    log.info("━━━ [NODE 2B / RESEARCHER] Agentic research loop starting")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[RESEARCHER] Skipping — SLA exceeded")
        return {"messages": [], "stream_chunks": [], "data_fetched": False}

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )
    pm_plan = state.get("pm_plan", "")

    data_needed_match = DATA_NEEDED_EXTRACT.search(pm_plan)
    data_needed = data_needed_match.group(1).strip() if data_needed_match else ""
    log.info(f"[RESEARCHER] DATA_NEEDED from plan: '{data_needed}'")

    if data_needed.lower() in ("none", "n/a", ""):
        log.info("[RESEARCHER] No data needed per PM plan — skipping")
        return {"messages": [], "stream_chunks": [], "data_fetched": True}

    collected_results: list[str] = []
    all_tool_messages: list = []
    all_ai_messages: list = []
    iteration = 0

    while iteration < RESEARCHER_MAX_ITERATIONS:
        if _sla_exceeded(state):
            log.warning("[RESEARCHER] SLA exceeded mid-loop — stopping")
            break

        iteration += 1
        log.info(f"[RESEARCHER] Iteration {iteration}/{RESEARCHER_MAX_ITERATIONS}")

        # ── Step 1: Decide what to call next ─────────────────────────────────
        context_so_far = (
            "\n---\n".join(collected_results)
            if collected_results
            else "NO TOOLS CALLED YET — you must make a CALL"
        )

        no_tools_yet_hint = (
            "NO TOOLS HAVE BEEN CALLED YET. You MUST output a CALL line. DONE is not valid."
            if not collected_results
            else "Output DONE only if collected results fully answer the question."
        )
        planner_system = RESEARCHER_PLANNER_PROMPT.format(
            no_tools_yet_hint=no_tools_yet_hint
        )

        planner_user = (
            f"Question: {user_msg[:RESEARCHER_QUESTION_WINDOW]}\n"
            f"Need: {data_needed[:RESEARCHER_NEED_WINDOW]}\n"
            f"Have: {context_so_far[:RESEARCHER_CONTEXT_WINDOW]}"
        )

        try:
            planner_resp = llm_medium.invoke([
                SystemMessage(content=planner_system),
                HumanMessage(content=planner_user),
            ])
            lines = _llm_text(planner_resp).strip().splitlines()
            if not lines:
                log.warning("[RESEARCHER] Planner returned empty response — stopping")
                break
            decision = lines[0].strip()
            log.info(f"[RESEARCHER] Planner decision: {_truncate(decision, 150)}")
        except Exception as e:
            log.error(f"[RESEARCHER] Planner LLM failed: {e}", exc_info=True)
            break

        # ── Step 2: Parse decision ────────────────────────────────────────────
        decision_upper = decision.upper()

        if decision_upper.startswith("DONE"):
            if not collected_results:
                log.warning("[RESEARCHER] Planner said DONE with no results — stopping")
            else:
                log.info("[RESEARCHER] Planner says DONE — stopping")
            break

        if not decision_upper.startswith("CALL:"):
            log.warning(f"[RESEARCHER] Unrecognised format: '{decision[:80]}' — stopping")
            break

        try:
            after_call = decision[5:].strip()
            pipe_idx = after_call.index("|")
            tool_name = after_call[:pipe_idx].strip()
            args_str = after_call[pipe_idx + 1:].strip()
            tool_args = json.loads(args_str)
            log.info(f"[RESEARCHER] Parsed call: {tool_name}({tool_args})")
        except Exception as e:
            log.warning(f"[RESEARCHER] Failed to parse '{decision[:80]}': {e} — stopping")
            break

        # ── Step 3: Execute tool ──────────────────────────────────────────────
        fn = TOOL_MAP.get(tool_name)
        if not fn:
            log.warning(f"[RESEARCHER] Unknown tool '{tool_name}' — stopping")
            break

        tool_id = f"tc_{tool_name}_{int(time.time()*1000)}_{iteration}"
        all_ai_messages.append(AIMessage(content="", tool_calls=[{
            "name": tool_name,
            "args": tool_args,
            "id": tool_id,
            "type": "tool_call",
        }]))

        t1 = time.time()
        try:
            result = fn.invoke(tool_args)
            result_str = result if isinstance(result, str) else json.dumps(result)
            log.info(
                f"[RESEARCHER] {tool_name} → {len(result_str)} chars "
                f"in {time.time()-t1:.2f}s: {_truncate(result_str)}"
            )
        except Exception as e:
            log.error(f"[RESEARCHER] Tool '{tool_name}' raised: {e}", exc_info=True)
            result_str = f"Tool error: {str(e)}"

        trimmed = result_str[:MAX_PROMPT_CHARS]
        all_tool_messages.append(ToolMessage(content=trimmed, tool_call_id=tool_id))

        # ── Step 4: Check for soft errors ────────────────────────────────────
        if _is_tool_result_an_error(result_str):
            log.warning("[RESEARCHER] Result is an error — noting and continuing")
            collected_results.append(f"[{tool_name} failed]: {result_str[:200]}")
            continue

        collected_results.append(trimmed)
        # Planner will say DONE on the next iteration if data is sufficient.
        # No second LLM call needed — the planner already receives context_so_far.

    data_fetched = len(collected_results) > 0
    log.info(
        f"[RESEARCHER] ✓ Done in {time.time()-t0:.2f}s | "
        f"{iteration} iteration(s) | {len(collected_results)} good result(s) | "
        f"{len(all_tool_messages)} ToolMessage(s) | data_fetched={data_fetched}"
    )

    return {
        "messages": all_ai_messages + all_tool_messages,
        "stream_chunks": [],
        "data_fetched": data_fetched,
    }
