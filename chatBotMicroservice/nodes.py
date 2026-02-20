import json
import logging
import time
import queue
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_ollama import ChatOllama
from httpx import Timeout as HttpxTimeout
from state import AgentState
from tools import TOOLS, TOOL_MAP, USER_DISPLAY_TOOLS, CONTEXT_TOOLS

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent")

# Hard limits
NODE_TIMEOUT_SECS = 15
GRAPH_SLA_SECS = 30
MAX_PROMPT_CHARS = 4000
MAX_MESSAGES = 6  # bumped from 4 — tool messages need to survive trim

# =============================================================================
# LLM CLIENTS
# =============================================================================

# CPU-optimised — fast planner/router, kept small and snappy
# num_ctx=1024:     less memory pressure on CPU, enough for planning tasks
# num_predict=100:  short outputs only — this model just routes/plans
# num_thread=4:     avoid over-subscribing CPU cores (tune to your core count)
# repeat_penalty=1.1: light repetition guard without quality cost
# keep_alive="10m": stay warm between requests to avoid cold-start on CPU
llm_fast = ChatOllama(
    model="qwen3:1.7b",
    num_ctx=1024,
    num_predict=100,
    num_thread=4,
    repeat_penalty=1.1,
    keep_alive="10m",
    client_kwargs={
        "timeout": HttpxTimeout(connect=5.0, read=28.0, write=5.0, pool=5.0)
    },
)

# CPU-optimised — quality responder on qwen3:4b
# num_ctx=3072:      enough for tool context + conversation without OOM on CPU
# num_predict=400:   balanced — full answers without running forever on CPU
# num_thread=6:      4b needs more threads to stay within 30s; tune to core count
# repeat_penalty=1.15: slightly stronger — 4b can get repetitive on CPU
# temperature=0.7:   balanced creativity vs. consistency
# keep_alive="10m":  keep warm, 4b has a noticeable cold-start on CPU
llm_respond = ChatOllama(
    model="qwen3:4b",
    num_ctx=3072,
    num_predict=400,
    num_thread=6,
    repeat_penalty=1.15,
    temperature=0.7,
    keep_alive="10m",
    client_kwargs={
        "timeout": HttpxTimeout(connect=5.0, read=28.0, write=5.0, pool=5.0)
    },
)

llm_fast_with_tools = llm_fast.bind_tools(TOOLS)

# =============================================================================
# HELPERS
# =============================================================================

def emit(type: str, data: str | list | dict) -> str:
    return json.dumps({"type": type, "data": data}) + "\n"


def _truncate(text: str, max: int = 120) -> str:
    text = str(text)
    return text if len(text) <= max else text[:max] + "..."


def _trim_messages(messages: list, max_messages: int = MAX_MESSAGES) -> list:
    system = [m for m in messages if isinstance(m, SystemMessage)]
    rest = [m for m in messages if not isinstance(m, SystemMessage)]
    trimmed = rest[-max_messages:]
    total_chars = sum(len(str(m.content)) for m in system + trimmed)
    log.info(f"[TRIM] {len(messages)} → {len(system + trimmed)} messages | ~{total_chars} chars")
    if total_chars > MAX_PROMPT_CHARS:
        log.warning(f"[TRIM] Prompt exceeds {MAX_PROMPT_CHARS} chars — may be slow")
    return system + trimmed


def _sla_exceeded(state: AgentState) -> bool:
    start = state.get("start_time")
    if not start:
        return False
    elapsed = time.time() - start
    if elapsed > GRAPH_SLA_SECS:
        log.warning(f"[SLA] Budget exceeded — {elapsed:.1f}s > {GRAPH_SLA_SECS}s — triggering early exit")
        return True
    return False


# FIX 2: Helper to extract tool context from state messages so respond_node
# can incorporate it. Returns a string summary of all ToolMessage contents.
def _extract_tool_context(messages: list) -> str:
    contexts = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.content:
            contexts.append(msg.content)
    return "\n\n".join(contexts) if contexts else ""


# =============================================================================
# AGENT 1 — Reason
# Streams thinking tokens live into token_queue AND into stream_chunks
# =============================================================================

def reason_node(state: AgentState) -> AgentState:
    log.info("━━━ [AGENT 1 / REASON] Decomposing prompt")
    t0 = time.time()

    if _sla_exceeded(state):
        fallback = "Responding directly."
        token_queue: queue.Queue = state.get("token_queue")
        if token_queue:
            token_queue.put(emit("thinking_content", fallback))
            token_queue.put("__thinking_done__")
        return {
            "messages": [],
            "reasoning_summary": "SLA exceeded.",
            "stream_chunks": [emit("thinking_content", fallback)],
            "display_results": [],
        }

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )
    log.info(f"[REASON] Prompt: {_truncate(user_msg)}")

    token_queue: queue.Queue = state.get("token_queue")
    breakdown = ""
    thinking_chunks = []

    # FIX 3: Improved reason prompt — explicitly calls out tool availability
    # and asks the model to identify WHAT kind of answer is needed (conceptual
    # explanation vs. data/chart vs. both) so plan_tools can act on it.
    try:
        for chunk in llm_fast.stream([
            SystemMessage(content=(
                "Decompose the user's request into a clear sequence of subproblems in at most 120 words.\n\n"
                "IMPORTANT: Always answer these three questions first:\n"
                "1. INTENT: Does the user want a conceptual explanation, a visual/chart, or both?\n"
                "2. DATA: Is external data, a tool, or a chart needed? (yes/no and why)\n"
                "3. STEPS: List the ordered steps to fully satisfy the request.\n\n"
                "Do NOT answer the question or perform calculations. "
                "State assumptions clearly when information is ambiguous."
            )),
            *_trim_messages(state["messages"]),
        ]):
            token = chunk.content or ""
            if token:
                breakdown += token
                chunk_str = emit("thinking_content", token)
                thinking_chunks.append(chunk_str)
                if token_queue:
                    token_queue.put(chunk_str)
    except Exception as e:
        log.error(f"[REASON] LLM call failed: {e}")
        breakdown = "Could not analyze request."
        fallback_chunk = emit("thinking_content", breakdown)
        thinking_chunks.append(fallback_chunk)
        if token_queue:
            token_queue.put(fallback_chunk)

    if token_queue:
        token_queue.put("__thinking_done__")

    log.info(f"[REASON] Done in {time.time() - t0:.2f}s | {len(breakdown)} chars")

    return {
        "messages": [],
        "reasoning_summary": breakdown,
        "stream_chunks": thinking_chunks,
        "display_results": [],
    }


# =============================================================================
# AGENT 2b — Tool Planner (DETERMINISTIC — no LLM, instant dispatch)
#
# Why: The LLM-based planner was taking 10+ seconds and still failing.
# For a 1.7b model running locally, tool-use via function calling is
# unreliable. We replace it with fast regex/keyword rules that are 100%
# predictable and complete in <1ms.
# =============================================================================

import re

# Map of keyword patterns → (tool_name, args)
# Evaluated in order — first match wins.
_GRAPH_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bscatter\b", re.I), "ScatterPlot"),
    (re.compile(r"\bline\s*(graph|chart|plot)?\b", re.I), "LineGraph"),
    (re.compile(r"\bbar\s*(graph|chart|plot)?\b", re.I), "BarGraph"),
    (re.compile(r"\bhistogram\b", re.I), "BarGraph"),
    # Generic "graph/chart/plot/visuali/show me/display/draw" — default scatter
    (re.compile(r"\b(graph|chart|plot|visuali|display|draw)\b", re.I), "ScatterPlot"),
]

_CONTEXT_RULES: list[re.Pattern] = [
    re.compile(r"\b(company|stock|ticker|corp|inc|ltd|revenue|earnings|ceo|founder)\b", re.I),
]

# Also check reasoning_summary for chart intent keywords
_REASONING_CHART_HINTS = re.compile(
    r"\b(visual|chart|graph|plot|scatter|line|bar|example)\b", re.I
)


def _detect_graph_type(text: str) -> str | None:
    for pattern, graph_type in _GRAPH_RULES:
        if pattern.search(text):
            return graph_type
    return None


def _needs_context(text: str) -> bool:
    return any(p.search(text) for p in _CONTEXT_RULES)


def plan_tools_node(state: AgentState) -> AgentState:
    log.info("━━━ [AGENT 2b / PLAN_TOOLS] Deterministic dispatch (no LLM)")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[PLAN_TOOLS] SLA exceeded — skipping")
        return {"messages": [], "stream_chunks": []}

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )
    reasoning = state.get("reasoning_summary", "")

    # Combine user message + reasoning for matching
    combined = f"{user_msg} {reasoning}"

    tool_calls = []

    # --- Chart detection ---
    graph_type = _detect_graph_type(combined)
    if graph_type:
        log.info(f"[PLAN_TOOLS] Chart rule matched → {graph_type}")
        tool_calls.append({
            "name": "get_graph_data",
            "args": {"graph_type": graph_type},
            "id": f"tc_graph_{int(t0)}",
            "type": "tool_call",
        })

    # --- Context detection ---
    if _needs_context(combined):
        # Extract a reasonable query — first 60 chars of user message
        query = user_msg[:60].strip()
        log.info(f"[PLAN_TOOLS] Context rule matched → query='{query}'")
        tool_calls.append({
            "name": "get_company_context",
            "args": {"query": query},
            "id": f"tc_ctx_{int(t0)}",
            "type": "tool_call",
        })

    log.info(f"[PLAN_TOOLS] Done in {(time.time() - t0)*1000:.1f}ms | {len(tool_calls)} tool(s)")

    if not tool_calls:
        log.info("[PLAN_TOOLS] No tools matched")
        return {"messages": [], "stream_chunks": []}

    # Build a synthetic AIMessage carrying tool_calls so tool_node can pick it up
    ai_msg = AIMessage(content="", tool_calls=tool_calls)
    return {"messages": [ai_msg], "stream_chunks": []}


# =============================================================================
# Tool Executor
# =============================================================================

def tool_node(state: AgentState) -> AgentState:
    log.info("━━━ [TOOLS] Executing tool calls")

    if _sla_exceeded(state):
        log.warning("[TOOLS] SLA exceeded — skipping")
        return {"messages": [], "display_results": [], "stream_chunks": []}

    last_ai = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", []):
            last_ai = msg
            break

    if not last_ai:
        log.info("[TOOLS] No tool calls found — skipping")
        return {"messages": [], "display_results": [], "stream_chunks": []}

    tool_messages = []
    display_results = []

    log.info(f"[TOOLS] {len(last_ai.tool_calls)} tool call(s)")

    for tc in last_ai.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_id = tc["id"]

        log.info(f"[TOOLS] → '{tool_name}' args: {tool_args}")
        t0 = time.time()

        fn = TOOL_MAP.get(tool_name)
        if not fn:
            log.warning(f"[TOOLS] No handler for '{tool_name}' — skipping")
            continue

        try:
            result = fn.invoke(tool_args)
        except Exception as e:
            log.warning(f"[TOOLS] '{tool_name}' failed: {e}")
            continue

        elapsed = time.time() - t0

        if tool_name in USER_DISPLAY_TOOLS:
            count = len(result) if isinstance(result, list) else 1
            log.info(f"[TOOLS] '{tool_name}' → DISPLAY | {count} item(s) | {elapsed:.2f}s")
            display_results.append(result)
            tool_messages.append(ToolMessage(
                content="Display data sent to frontend.",
                tool_call_id=tool_id,
            ))
        elif tool_name in CONTEXT_TOOLS:
            content = result if isinstance(result, str) else json.dumps(result)
            log.info(f"[TOOLS] '{tool_name}' → CONTEXT | {elapsed:.2f}s | {_truncate(content)}")
            tool_messages.append(ToolMessage(
                content=content[:MAX_PROMPT_CHARS],
                tool_call_id=tool_id,
            ))

    log.info(f"[TOOLS] Done — {len(display_results)} display, {len(tool_messages)} context")
    return {"messages": tool_messages, "display_results": display_results, "stream_chunks": []}


# =============================================================================
# AGENT 3a — Responder
# FIX 5: Now reads tool context from state messages and incorporates it.
# Also uses reasoning_summary to know what parts of the question to answer.
# =============================================================================

def respond_node(state: AgentState) -> AgentState:
    log.info("━━━ [AGENT 3a / RESPOND] Generating response")
    t0 = time.time()

    if _sla_exceeded(state):
        return {
            "messages": [],
            "stream_chunks": [emit("response_content",
                "I wasn't able to process your request in time. Please try again.")],
        }

    content = ""
    response = None

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )

    # Pull tool context (e.g. company info) so the response can reference it
    tool_context = _extract_tool_context(state["messages"])
    reasoning = state.get("reasoning_summary", "")

    # Did we send charts? Tell the model so it doesn't try to describe them.
    display_results = state.get("display_results", [])
    chart_note = (
        "A chart has already been rendered for the user — do NOT describe it or say you can't show one."
        if display_results
        else "No chart was rendered."
    )

    # Build the system prompt dynamically based on what happened upstream
    system_parts = [
        "You are a helpful assistant. Answer the user's question directly and concisely.",
        chart_note,
        "Max 4 sentences unless context data requires more.",
        "Do not repeat the user's question back. Do not list validation steps.",
    ]
    if tool_context:
        system_parts.append(f"\nRelevant context retrieved by tools:\n{tool_context[:1000]}")

    system_prompt = "\n".join(system_parts)

    # Build user turn: include reasoning so model knows what sub-questions to answer
    user_turn = user_msg
    if reasoning:
        user_turn = (
            f"{user_msg}\n\n"
            f"[Reasoning breakdown to guide your answer]:\n{reasoning[:400]}"
        )

    try:
        response = llm_respond.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_turn),
        ])
        content = response.content or ""
    except Exception as e:
        log.error(f"[RESPOND] LLM call failed: {e}")
        content = "I wasn't able to generate a response. Please try again."

    log.info(f"[RESPOND] Done in {time.time() - t0:.2f}s | {_truncate(content)}")

    return {
        "messages": [response] if response is not None else [],
        "stream_chunks": [emit("response_content", content)],
    }


# =============================================================================
# AGENT 3b — Display Decider
# =============================================================================

def display_decision_node(state: AgentState) -> AgentState:
    log.info("━━━ [AGENT 3b / DISPLAY] Evaluating display modules")
    display_results = state.get("display_results", [])

    if not display_results:
        log.info("[DISPLAY] No display results — skipping")
        return {"messages": [], "stream_chunks": [], "display_results": []}

    flat = []
    for r in display_results:
        flat.extend(r) if isinstance(r, list) else flat.append(r)

    if _sla_exceeded(state):
        log.warning("[DISPLAY] SLA exceeded — sending charts without LLM check")
        return {
            "messages": [],
            "stream_chunks": [emit("display_modules", flat)],
            "display_results": [],
        }

    chart_types = [r.get("type") for r in flat if isinstance(r, dict)]
    log.info(f"[DISPLAY] {len(flat)} chart(s): {chart_types}")
    t0 = time.time()

    try:
        verdict = llm_fast.invoke([
            SystemMessage(content=(
                "Reply with only 'send' or 'skip'. "
                "Are these charts relevant to the user's request?"
            )),
            HumanMessage(content=(
                f"Request summary: {state.get('reasoning_summary', '')[:300]}\n"
                f"Chart types: {chart_types}"
            )),
        ])
        decision = getattr(verdict, "content", "send").lower()
    except Exception as e:
        log.warning(f"[DISPLAY] LLM check failed: {e} — defaulting to send")
        decision = "send"

    log.info(f"[DISPLAY] Verdict: '{decision}' | {time.time() - t0:.2f}s")

    if "skip" not in decision:
        log.info(f"[DISPLAY] Emitting {len(flat)} chart(s)")
        return {
            "messages": [],
            "stream_chunks": [emit("display_modules", flat)],
            "display_results": [],
        }

    log.info("[DISPLAY] Charts skipped")
    return {"messages": [], "stream_chunks": [], "display_results": []}


# =============================================================================
# Merge — passthrough join point
# =============================================================================

def merge_parallel_node(state: AgentState) -> AgentState:
    elapsed = time.time() - state.get("start_time", time.time())
    log.info(f"━━━ [MERGE] Branches joined | {elapsed:.1f}s elapsed")
    return {"messages": [], "stream_chunks": []}


# =============================================================================
# EVALUATOR — opt-in via state["needs_validation"]
# =============================================================================

def evaluator_node(state: AgentState) -> AgentState:
    elapsed = time.time() - state.get("start_time", time.time())
    remaining = GRAPH_SLA_SECS - elapsed

    if not state.get("needs_validation", False):
        log.info(f"━━━ [EVALUATOR] Skipped | {elapsed:.1f}s elapsed")
        return {
            "evaluation": "pass",
            "messages": [],
            "stream_chunks": [],
            "display_results": [],
        }

    if remaining < 3:
        log.warning(f"[EVALUATOR] Only {remaining:.1f}s left — passing through")
        return {
            "evaluation": "pass",
            "messages": [],
            "stream_chunks": [],
            "display_results": [],
        }

    log.info(f"━━━ [EVALUATOR] Evaluating | {remaining:.1f}s budget remaining")
    t0 = time.time()

    last_response = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            last_response = msg.content
            break

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )

    result = "pass"
    try:
        verdict = llm_fast.invoke([
            SystemMessage(content="Reply with only 'pass' or 'fail' and one sentence why."),
            HumanMessage(content=(
                f"Request: {user_msg[:300]}\nResponse: {last_response[:500]}"
            )),
        ])
        result = "pass" if "pass" in getattr(verdict, "content", "pass").lower() else "fail"
    except Exception as e:
        log.warning(f"[EVALUATOR] LLM check failed: {e} — defaulting to pass")

    retry_count = state.get("retry_count", 0)
    log.info(f"[EVALUATOR] {result.upper()} | {time.time() - t0:.2f}s | retries: {retry_count}")

    return {
        "evaluation": result,
        "retry_count": retry_count + (1 if result == "fail" else 0),
        "messages": [],
        "stream_chunks": [],
        "display_results": [],
    }