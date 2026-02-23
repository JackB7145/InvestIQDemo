import json
import logging
import time
import queue
import re
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from state import AgentState
from tools import TOOL_MAP, USER_DISPLAY_TOOLS, CONTEXT_TOOLS
from models import llm_fast, llm_medium, llm_respond

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent")

# =============================================================================
# CONSTANTS
# =============================================================================

GRAPH_SLA_SECS = 180
MAX_PROMPT_CHARS = 4000
MAX_MESSAGES = 6
RESEARCHER_MAX_ITERATIONS = 3

# =============================================================================
# HELPERS
# =============================================================================

def emit(type: str, data) -> str:
    return json.dumps({"type": type, "data": data}) + "\n"

def _truncate(text: str, max: int = 120) -> str:
    text = str(text)
    return text if len(text) <= max else text[:max] + "..."

def _sla_exceeded(state: AgentState) -> bool:
    start = state.get("start_time")
    if not start:
        return False
    elapsed = time.time() - start
    if elapsed > GRAPH_SLA_SECS:
        log.warning(f"[SLA] {elapsed:.1f}s > {GRAPH_SLA_SECS}s — triggering early exit")
        return True
    return False

def _extract_tool_context(messages: list) -> str:
    return "\n\n".join(
        msg.content for msg in messages
        if isinstance(msg, ToolMessage) and msg.content
    )

def _llm_text(resp):
    if not resp:
        return ""
    log.debug(f"[_llm_text] type={type(resp).__name__} repr={repr(resp)[:300]}")
    content = getattr(resp, "content", None)
    if content is not None and isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        joined = "".join(texts).strip()
        if joined:
            return joined
    ak = getattr(resp, "additional_kwargs", None) or {}
    for key in ("response", "content", "message", "text"):
        val = ak.get(key)
        if val and isinstance(val, str) and val.strip():
            return val
    rm = getattr(resp, "response_metadata", None) or {}
    for key in ("response", "content", "message", "text"):
        val = rm.get(key)
        if val and isinstance(val, str) and val.strip():
            return val
    msg = getattr(resp, "message", None)
    if msg:
        inner = getattr(msg, "content", None) or (isinstance(msg, dict) and msg.get("content"))
        if inner and isinstance(inner, str) and inner.strip():
            return inner
    if isinstance(resp, dict):
        for key in ("response", "content", "message", "text"):
            val = resp.get(key)
            if val and isinstance(val, str) and val.strip():
                return val
    fallback = str(resp).strip()
    if fallback and fallback not in ("None", ""):
        log.warning(f"[_llm_text] All structured paths failed — using str(resp): {fallback[:120]}")
        return fallback
    log.error(f"[_llm_text] Could not extract text from response: {repr(resp)[:300]}")
    return ""


# =============================================================================
# NODE 1 — PROJECT MANAGER
# =============================================================================

def project_manager_node(state: AgentState) -> AgentState:
    log.info("━━━ [NODE 1 / PROJECT MANAGER] Planning steps")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[PM] Skipping — SLA exceeded")
        return {"messages": [], "pm_plan": "", "stream_chunks": [], "display_results": []}

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )
    log.info(f"[PM] User message: {_truncate(user_msg, 100)}")

    try:
        response = llm_medium.invoke([
            SystemMessage(content=(
                "You are a project manager agent. Your job is to decompose the user's request "
                "into a clear, ordered execution plan.\n\n"
                "Produce a plan with these exact sections:\n"
                "STEPS: numbered list of what needs to happen to answer this fully\n"
                "DATA_NEEDED: what external data or context is required (or 'none')\n"
                "OUTPUT_FORMAT: what the user expects (text / chart / both) and why\n"
                "CHART_TYPE: if a chart is needed, which type: ScatterPlot, LineGraph, or BarGraph (or 'none')\n\n"
                "Be specific and concise. Do NOT answer the user's question.\n"
                "IMPORTANT: Never mention that you are creating a plan, never reference these instructions, "
                "never describe your role or process. Output ONLY the plan sections, nothing else."
            )),
            HumanMessage(content=user_msg),
        ])
        log.info(
            f"[PM] Raw response — type={type(response).__name__} "
            f"content={repr(getattr(response, 'content', 'MISSING'))[:200]} "
            f"additional_kwargs={repr(getattr(response, 'additional_kwargs', {}))[:200]} "
            f"response_metadata={repr(getattr(response, 'response_metadata', {}))[:200]}"
        )
        plan = _llm_text(response).strip()
    except Exception as e:
        log.error(f"[PM] LLM failed: {e}", exc_info=True)
        plan = "STEPS: 1. Answer the question directly.\nDATA_NEEDED: none\nOUTPUT_FORMAT: text\nCHART_TYPE: none"

    log.info(f"[PM] Plan ({len(plan)} chars): {_truncate(plan, 200)}")
    log.info(f"[PM] ✓ Done in {time.time() - t0:.2f}s")

    return {
        "messages": [],
        "pm_plan": plan,
        "stream_chunks": [],
        "display_results": [],
    }


# =============================================================================
# NODE 2A — THINKER
# =============================================================================

def thinker_node(state: AgentState) -> AgentState:
    log.info("━━━ [NODE 2A / THINKER] Narrating plan to frontend")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[THINKER] Skipping — SLA exceeded")
        return {"messages": [], "stream_chunks": []}

    pm_plan = state.get("pm_plan", "")
    token_queue: queue.Queue = state.get("token_queue")

    log.info(
        f"[THINKER] pm_plan present: {bool(pm_plan)} | "
        f"token_queue: {token_queue is not None}"
    )

    if not pm_plan:
        log.warning("[THINKER] No PM plan available — skipping")
        if token_queue:
            token_queue.put("__thinking_done__")
        return {"messages": [], "stream_chunks": []}

    thinking_chunks = []

    try:
        log.info("[THINKER] Invoking llm_fast")
        response = llm_fast.invoke([
            SystemMessage(content=(
                "You are a thinking narrator. Read the plan below and restate it "
                "in simple, conversational language as if thinking out loud. "
                "Use first person: 'First I'll...', 'Then I need to...', "
                "'I can see that...'. Keep it under 60 words. "
                "Do not use bullet points or headers. "
                "Never mention that you are reading a plan, never reference instructions or your process."
            )),
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


# =============================================================================
# NODE 2B — RESEARCHER
# =============================================================================

_DATA_NEEDED_EXTRACT = re.compile(r"DATA_NEEDED:\s*(.+?)(?:\n|$)", re.I)
_CHART_TYPE_EXTRACT  = re.compile(r"CHART_TYPE:\s*(\w+)", re.I)


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

    data_needed_match = _DATA_NEEDED_EXTRACT.search(pm_plan)
    data_needed = data_needed_match.group(1).strip() if data_needed_match else ""
    log.info(f"[RESEARCHER] DATA_NEEDED from plan: '{data_needed}'")

    if data_needed.lower() in ("none", "n/a", ""):
        log.info("[RESEARCHER] No data needed per PM plan — skipping")
        return {"messages": [], "stream_chunks": [], "data_fetched": True}  # no data needed = not a failure

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
        context_so_far = "\n---\n".join(collected_results) if collected_results else "NO TOOLS CALLED YET — you must make a CALL"

        planner_system = (
            "You are a research tool router. Output ONE line only. No explanation.\n"
            "Format options:\n"
            "  CALL: get_company_context | {\"query\": \"<topic>\"}\n"
            "  CALL: get_stock_data | {\"symbol\": \"<TICKER>\", \"function\": \"<FUNCTION>\"}\n"
            "  DONE\n"
            "get_stock_data functions: OVERVIEW, GLOBAL_QUOTE, TIME_SERIES_DAILY, "
            "INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, EARNINGS\n"
            + (
                "NO TOOLS HAVE BEEN CALLED YET. You MUST output a CALL line. DONE is not valid."
                if not collected_results else
                "Output DONE only if collected results fully answer the question."
            )
        )

        planner_user = (
            f"Question: {user_msg[:300]}\n"
            f"Need: {data_needed[:200]}\n"
            f"Have: {context_so_far[:600]}"
        )

        try:
            planner_resp = llm_medium.invoke([
                SystemMessage(content=planner_system),
                HumanMessage(content=planner_user),
            ])
            decision = _llm_text(planner_resp).strip().splitlines()[0].strip()
            log.info(f"[RESEARCHER] Planner decision: {_truncate(decision, 150)}")
        except Exception as e:
            log.error(f"[RESEARCHER] Planner LLM failed: {e}", exc_info=True)
            break

        # ── Step 2: Parse decision ────────────────────────────────────────────
        decision_upper = decision.upper()

        # Block DONE on iteration 1 — nothing has been fetched yet
        if decision_upper.startswith("DONE"):
            if not collected_results:
                log.warning("[RESEARCHER] Planner said DONE with no results — ignoring and stopping")
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
            log.info(f"[RESEARCHER] {tool_name} → {len(result_str)} chars in {time.time()-t1:.2f}s: {_truncate(result_str)}")
        except Exception as e:
            log.error(f"[RESEARCHER] Tool '{tool_name}' raised: {e}", exc_info=True)
            result_str = f"Tool error: {str(e)}"

        trimmed = result_str[:MAX_PROMPT_CHARS]
        all_tool_messages.append(ToolMessage(content=trimmed, tool_call_id=tool_id))

        # ── Step 4: Check for soft errors ────────────────────────────────────
        if _is_tool_result_an_error(result_str):
            log.warning(f"[RESEARCHER] Result is an error — noting and continuing")
            collected_results.append(f"[{tool_name} failed]: {result_str[:200]}")
            continue

        collected_results.append(trimmed)

        # ── Step 5: Sufficiency check ─────────────────────────────────────────
        check_user = (
            f"Question: {user_msg[:200]}\n"
            f"Need: {data_needed[:150]}\n"
            f"Have: {trimmed[:400]}\n"
            f"Reply SUFFICIENT or INSUFFICIENT only."
        )

        try:
            check_resp = llm_fast.invoke([
                SystemMessage(content="Reply with one word: SUFFICIENT or INSUFFICIENT."),
                HumanMessage(content=check_user),
            ])
            verdict = _llm_text(check_resp).strip().upper()
            verdict = "SUFFICIENT" if "SUFFICIENT" in verdict else "INSUFFICIENT"
            log.info(f"[RESEARCHER] Sufficiency: {verdict}")
        except Exception as e:
            log.warning(f"[RESEARCHER] Sufficiency check failed: {e} — assuming SUFFICIENT")
            verdict = "SUFFICIENT"

        if verdict == "SUFFICIENT":
            log.info("[RESEARCHER] Sufficient — stopping loop")
            break
        else:
            log.info("[RESEARCHER] Insufficient — looping")

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


# =============================================================================
# NODE 3 — DISPLAY AGENT
# =============================================================================

_GRAPH_TYPE_MAP = {
    "scatterplot": "ScatterPlot",
    "scatter":     "ScatterPlot",
    "linegraph":   "LineGraph",
    "line":        "LineGraph",
    "bargraph":    "BarGraph",
    "bar":         "BarGraph",
    "histogram":   "BarGraph",
}


def display_agent_node(state: AgentState) -> AgentState:
    log.info("━━━ [NODE 3 / DISPLAY AGENT] Determining visuals")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[DISPLAY] Skipping — SLA exceeded")
        return {"messages": [], "display_results": [], "stream_chunks": []}

    pm_plan = state.get("pm_plan", "")
    chart_match = _CHART_TYPE_EXTRACT.search(pm_plan)
    raw_type = chart_match.group(1).strip().lower() if chart_match else "none"
    log.info(f"[DISPLAY] CHART_TYPE from PM plan: '{raw_type}'")

    graph_type = _GRAPH_TYPE_MAP.get(raw_type)
    if not graph_type:
        log.info("[DISPLAY] No chart needed per PM plan — skipping")
        return {"messages": [], "display_results": [], "stream_chunks": []}

    # ── Step 1: Get the schema template ──────────────────────────────────────
    schema_fn = TOOL_MAP.get("get_graph_data")
    if not schema_fn:
        log.error("[DISPLAY] No handler for 'get_graph_data' in TOOL_MAP")
        return {"messages": [], "display_results": [], "stream_chunks": []}

    try:
        schemas = schema_fn.invoke({"graph_type": graph_type})
        schema_template = schemas[0] if schemas else {}
        log.info(f"[DISPLAY] Got schema template for {graph_type}")
    except Exception as e:
        log.error(f"[DISPLAY] get_graph_data failed: {e}", exc_info=True)
        return {"messages": [], "display_results": [], "stream_chunks": []}

    # ── Step 2: Gather research context ──────────────────────────────────────
    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )
    tool_context = _extract_tool_context(state["messages"])
    log.info(f"[DISPLAY] Tool context available: {len(tool_context)} chars")

    if not tool_context:
        log.warning("[DISPLAY] No research context — LLM will use its own knowledge")

    # ── Step 3: LLM fills the schema with real data ───────────────────────────
    fill_system = (
        "You are a data formatter. Output ONLY valid JSON. No explanation, no markdown, no code fences.\n\n"
        "Fill this chart template with real data. STRICT RULES:\n"
        "- Output must be a single JSON object with exactly this shape:\n"
        "  {\"type\": \"LineGraph\", \"data\": {\"title\": \"...\", \"data\": [...], \"series\": [...]}}\n"
        "- Each object in \"data\" array must have a \"name\" string field and ONE OR MORE numeric fields\n"
        "- The numeric field names must be simple words like \"close\", \"price\", \"value\" — NOT dollar amounts or symbols\n"
        "- series[].key must exactly match one of those numeric field names\n"
        "- Example data object: {\"name\": \"2024-01-15\", \"close\": 185.92}\n"
        "- Example series: [{\"key\": \"close\", \"color\": \"#1976d2\"}]\n"
        "- Only use numbers from the research context — do NOT invent data\n"
        "- Include between 7 and 28 data points maximum — do not exceed this or the JSON will be truncated\n"
        "- Output ONLY the JSON object, nothing else"
    )

    fill_user = (
        f"User request: {user_msg[:300]}\n\n"
        f"Research context:\n{tool_context[:1500] if tool_context else 'No data available.'}\n\n"
        f"Template to fill:\n{json.dumps(schema_template, indent=2)}\n\n"
        f"Remember: numeric field names must be simple words (e.g. 'close', 'price'), not dollar values.\n"
        f"Output the filled JSON object:"
    )

    display_results = []
    tool_messages = []
    tool_id = f"tc_graph_{int(t0 * 1000)}"
    ai_msg = AIMessage(content="", tool_calls=[{
        "name": "get_graph_data",
        "args": {"graph_type": graph_type},
        "id": tool_id,
        "type": "tool_call",
    }])

    try:
        fill_resp = llm_respond.invoke([
            SystemMessage(content=fill_system),
            HumanMessage(content=fill_user),
        ])
        raw_json = _llm_text(fill_resp).strip()
        raw_json = re.sub(r"^```[a-z]*\n?", "", raw_json).rstrip("`").strip()
        log.info(f"[DISPLAY] LLM raw output: {_truncate(raw_json, 300)}")

        chart_obj = json.loads(raw_json)

        assert "type" in chart_obj, "Missing 'type'"
        assert "data" in chart_obj, "Missing top-level 'data'"
        inner = chart_obj["data"]
        assert isinstance(inner, dict), "'data' must be a dict"
        assert "data" in inner, "Missing 'data.data' array"
        assert "series" in inner, "Missing 'data.series' array"
        assert isinstance(inner["data"], list), "'data.data' must be a list"
        assert len(inner["data"]) > 0, "'data.data' is empty"
        # Ensure series keys actually exist in data objects
        data_keys = set(inner["data"][0].keys()) - {"name"}
        for s in inner["series"]:
            key = s.get("key") or s.get("xKey") or s.get("yKey")
            assert key in inner["data"][0] or key in {"x","y"}, f"Series key '{key}' not found in data objects"

        display_results.append(chart_obj)
        tool_messages.append(ToolMessage(
            content="Chart filled and sent to frontend.",
            tool_call_id=tool_id,
        ))
        log.info(f"[DISPLAY] ✓ Chart ready — {len(chart_obj['data']['data'])} data points, title='{chart_obj['data'].get('title')}'")

    except json.JSONDecodeError as e:
        log.error(f"[DISPLAY] Invalid JSON from LLM: {e} | raw: {_truncate(raw_json, 300)}")
        tool_messages.append(ToolMessage(content="Chart failed — bad JSON.", tool_call_id=tool_id))
    except AssertionError as e:
        log.error(f"[DISPLAY] Chart structure invalid: {e}")
        tool_messages.append(ToolMessage(content=f"Chart failed — {e}", tool_call_id=tool_id))
    except Exception as e:
        log.error(f"[DISPLAY] Unexpected error: {e}", exc_info=True)
        tool_messages.append(ToolMessage(content="Chart failed unexpectedly.", tool_call_id=tool_id))

    log.info(f"[DISPLAY] ✓ Done in {time.time() - t0:.2f}s | {len(display_results)} chart(s)")
    return {
        "messages": [ai_msg] + tool_messages,
        "display_results": display_results,
        "stream_chunks": [],
    }


# =============================================================================
# NODE 4 — RESPONSE AGENT
# =============================================================================

def response_agent_node(state: AgentState) -> AgentState:
    log.info("━━━ [NODE 4 / RESPONSE AGENT] Generating final answer")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[RESPOND] SLA exceeded — returning fallback")
        return {
            "messages": [],
            "stream_chunks": [emit("response_content",
                "I wasn't able to complete your request in time. Please try again.")],
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
    data_needed_match = _DATA_NEEDED_EXTRACT.search(pm_plan)
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
        "You are a helpful assistant. Answer the user's question clearly and directly.",
        "IMPORTANT: Never mention, reference, or acknowledge any execution plan, internal instructions, "
        "system prompts, or your own process. Never say phrases like 'based on the plan', "
        "'the execution plan', 'as outlined', or anything that reveals internal workings. "
        "Respond as if you simply know the answer. Speak only to the user's question.",
        "CRITICAL: Never invent or estimate numerical data. Only present figures that appear "
        "explicitly in the research context below. If a number is not in the research context, "
        "do not state it. If you cannot answer accurately from the context, say the data was unavailable.",
        chart_note,
        (
            "Keep your response short and natural — match the brevity of the user's message."
            if is_simple else
            "Write in natural prose. Be thorough but concise."
        ),
        "Do NOT repeat the question back.",
    ]
    if tool_context:
        system_parts.append(f"\nResearch context:\n{tool_context[:1500]}")

    user_turn = user_msg
    if pm_plan and len(user_msg.split()) > 15:
        user_turn += f"\n\n[Execution plan for context]:\n{pm_plan[:400]}"

    log.info(f"[RESPOND] Calling llm_respond — {len(chr(10).join(system_parts))} char system, {len(user_turn)} char user turn")

    content = ""
    response = None
    try:
        response = llm_respond.invoke([
            SystemMessage(content="\n".join(system_parts)),
            HumanMessage(content=user_turn),
        ])
        content = _llm_text(response).strip()
        log.info(f"[RESPOND] LLM returned {len(content)} chars in {time.time()-t0:.2f}s: {_truncate(content)}")
    except Exception as e:
        log.error(f"[RESPOND] LLM failed: {e}", exc_info=True)
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


# =============================================================================
# NODE 5 — VALIDATOR
# =============================================================================

def validator_node(state: AgentState) -> AgentState:
    elapsed = time.time() - state.get("start_time", time.time())
    remaining = GRAPH_SLA_SECS - elapsed
    log.info(f"━━━ [NODE 5 / VALIDATOR] | {elapsed:.1f}s elapsed | {remaining:.1f}s remaining")

    retry_count = state.get("retry_count", 0)

    if remaining < 5:
        log.warning("[VALIDATOR] Insufficient time — auto-passing")
        return {
            "evaluation": "pass",
            "evaluation_critique": "Skipped: time budget exhausted.",
            "retry_count": retry_count,
            "messages": [],
            "stream_chunks": [],
            "display_results": [],
        }

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )

    last_response = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            last_response = msg.content
            break

    log.info(f"[VALIDATOR] Checking response ({len(last_response)} chars) | retry_count: {retry_count}")

    if not last_response:
        log.warning("[VALIDATOR] No response found — auto-failing")
        return {
            "evaluation": "fail",
            "evaluation_critique": "No response was generated.",
            "retry_count": retry_count + 1,
            "messages": [],
            "stream_chunks": [],
            "display_results": [],
        }

    result = "pass"
    critique = ""
    t0 = time.time()

    try:
        verdict = llm_fast.invoke([
            SystemMessage(content=(
                "You are a strict quality validator. Reply ONLY with valid JSON:\n"
                '{"result": "pass", "critique": "one sentence"}\n'
                "or\n"
                '{"result": "fail", "critique": "one sentence why it failed"}\n\n'
                "FAIL if: response is empty, nonsensical, doesn't address the question, "
                "or is truncated mid-sentence.\n"
                "PASS if: response is complete and addresses the user's question."
            )),
            HumanMessage(content=(
                f"User question: {user_msg[:200]}\n\n"
                f"Response to validate:\n{last_response[:600]}"
            )),
        ])
        verdict_text = _llm_text(verdict)
        raw = re.sub(r"```[a-z]*\n?", "", verdict_text or "{}").strip().rstrip("`")
        log.info(f"[VALIDATOR] Raw LLM output: {repr(raw[:120])}")
        parsed = json.loads(raw)
        result = parsed.get("result", "pass").lower()
        critique = parsed.get("critique", "")
        if result not in ("pass", "fail"):
            result = "pass"
    except json.JSONDecodeError as e:
        log.warning(f"[VALIDATOR] JSON parse failed: {e} — defaulting to pass")
    except Exception as e:
        log.warning(f"[VALIDATOR] LLM check failed: {e} — defaulting to pass")

    new_retry = retry_count + (1 if result == "fail" else 0)
    log.info(f"[VALIDATOR] ✓ {result.upper()} | '{critique}' | {time.time()-t0:.2f}s | retries: {retry_count} → {new_retry}")

    if result == "fail" and new_retry >= 2:
        log.warning("[VALIDATOR] Max retries (2) reached — forcing pass")
        result = "pass"

    return {
        "evaluation": result,
        "evaluation_critique": critique,
        "retry_count": new_retry,
        "messages": [],
        "stream_chunks": [],
        "display_results": [],
    }