import json
import time
import re
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


# ─────────────────────────────────────────────────────────────
# JSON SANITIZER (critical fix)
# ─────────────────────────────────────────────────────────────

def _sanitize_tool_json(raw: str) -> dict:
    """
    Attempts to coerce malformed LLM JSON into valid structured args.
    Handles:
    - single quotes
    - unquoted keys
    - nested {"query": "{...}"} patterns
    - trailing commas
    """
    raw = raw.strip()

    # Extract inner JSON if wrapped in {"query": "{...}"}
    try:
        temp = json.loads(raw)
        if isinstance(temp, dict) and "query" in temp and isinstance(temp["query"], str):
            raw = temp["query"]
    except Exception:
        pass

    # Replace single quotes with double quotes
    raw = raw.replace("'", '"')

    # Quote unquoted keys: function= → "function":
    raw = re.sub(r'(\b\w+\b)\s*=', r'"\1":', raw)

    # Quote bare keys: function: → "function":
    raw = re.sub(r'(?<!")(\b\w+\b)\s*:', r'"\1":', raw)

    # Remove trailing commas
    raw = re.sub(r",(\s*[}\]])", r"\1", raw)

    return json.loads(raw)


def _is_tool_result_an_error(result: str) -> bool:
    error_markers = [
        "Error Message",
        "Thank you for using Alpha Vantage",
        "Information:",
        "not found",
        "No content found",
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
        return {"messages": [], "stream_chunks": [], "data_fetched": True}

    collected_results = []
    all_tool_messages = []
    all_ai_messages = []
    iteration = 0
    tool_called = False  # track if a tool has been called

    while iteration < RESEARCHER_MAX_ITERATIONS:
        if _sla_exceeded(state):
            break

        # Stop after the first successful tool call
        if tool_called:
            log.info("[RESEARCHER] Tool already called — stopping further iterations")
            break

        iteration += 1
        log.info(f"[RESEARCHER] Iteration {iteration}/{RESEARCHER_MAX_ITERATIONS}")

        context_so_far = (
            "\n---\n".join(collected_results)
            if collected_results
            else "NO TOOLS CALLED YET — you must make a CALL"
        )

        no_tools_yet_hint = (
            "You MUST output a CALL line. DONE is not valid."
            if not collected_results
            else "Output DONE only if results fully answer the question."
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
            decision = _llm_text(planner_resp).strip().splitlines()[0]
            log.info(f"[RESEARCHER] Planner decision: {_truncate(decision,150)}")
        except Exception as e:
            log.error(f"[RESEARCHER] Planner failed: {e}", exc_info=True)
            break

        decision_upper = decision.upper()

        if decision_upper.startswith("DONE"):
            break

        if not decision_upper.startswith("CALL:"):
            log.warning(f"[RESEARCHER] Invalid format: {decision}")
            break

        try:
            after_call = decision[5:].strip()
            tool_name, args_str = after_call.split("|", 1)
            tool_name = tool_name.strip()
            args_str = args_str.strip()

            # Extract limit if specified (e.g., limit=7)
            limit_match = re.search(r"limit\s*=\s*(\d+)", args_str, re.IGNORECASE)
            limit = int(limit_match.group(1)) if limit_match else None

            tool_args = _sanitize_tool_json(args_str)
            if limit is not None:
                tool_args["limit"] = limit  # pass to the tool

            log.info(f"[RESEARCHER] Parsed call: {tool_name}({tool_args})")

        except Exception as e:
            log.warning(f"[RESEARCHER] Failed to parse tool args: {e}")
            break

        fn = TOOL_MAP.get(tool_name)
        if not fn:
            log.warning(f"[RESEARCHER] Unknown tool '{tool_name}'")
            break

        tool_id = f"tc_{tool_name}_{int(time.time()*1000)}_{iteration}"

        all_ai_messages.append(AIMessage(content="", tool_calls=[{
            "name": tool_name,
            "args": tool_args,
            "id": tool_id,
            "type": "tool_call",
        }]))

        try:
            result = fn.invoke(tool_args)
            result_str = result if isinstance(result, str) else json.dumps(result)
        except Exception as e:
            log.error(f"[RESEARCHER] Tool error: {e}", exc_info=True)
            result_str = f"Tool error: {str(e)}"

        trimmed = result_str[:MAX_PROMPT_CHARS]

        all_tool_messages.append(ToolMessage(
            content=trimmed,
            tool_call_id=tool_id,
        ))

        collected_results.append(trimmed)
        tool_called = True  # mark that a tool has been called

    data_fetched = len(collected_results) > 0

    log.info(
        f"[RESEARCHER] ✓ Done in {time.time()-t0:.2f}s | "
        f"{iteration} iteration(s) | {len(collected_results)} result(s)"
    )

    return {
        "messages": all_ai_messages + all_tool_messages,
        "stream_chunks": [],
        "data_fetched": data_fetched,
    }