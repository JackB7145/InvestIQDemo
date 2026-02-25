import json
import time
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from state import AgentState
from models import llm_respond
from tools import TOOL_MAP
from nodes.helpers import (
    log, _sla_exceeded, _llm_text, _truncate,
    CHART_TYPE_EXTRACT,
    RESPOND_TOOL_CONTEXT_WINDOW,
    _extract_tool_context,
    extract_json_object,
)
from nodes.prompts import DISPLAY_FILL_PROMPT

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
    chart_match = CHART_TYPE_EXTRACT.search(pm_plan)
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
    if tool_context:
        context_section = f"Research context (use these numbers):\n{tool_context[:RESPOND_TOOL_CONTEXT_WINDOW]}"
        data_instruction = "Only use numbers from the research context — do NOT invent data."
    else:
        context_section = "Research context: None available. Use realistic sample values to illustrate the chart."
        data_instruction = "No real data is available — use plausible illustrative values."

    fill_user = (
        f"User request: {user_msg[:300]}\n\n"
        f"{context_section}\n\n"
        f"Template to fill:\n{json.dumps(schema_template, indent=2)}\n\n"
        f"{data_instruction}\n"
        f"Remember: numeric field names must be simple words (e.g. 'value', 'price'), not dollar amounts.\n"
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
            SystemMessage(content=DISPLAY_FILL_PROMPT),
            HumanMessage(content=fill_user),
        ])
        raw_text = _llm_text(fill_resp).strip()
        raw_json = extract_json_object(raw_text)
        log.info(f"[DISPLAY] LLM raw output: {_truncate(raw_json, 300)}")

        chart_obj = json.loads(raw_json)

        # Explicit validation instead of assertions
        if "type" not in chart_obj:
            raise ValueError("LLM chart output missing 'type' field")
        if "data" not in chart_obj:
            raise ValueError("LLM chart output missing top-level 'data' field")
        inner = chart_obj["data"]
        if not isinstance(inner, dict):
            raise ValueError(f"'data' must be a dict, got {type(inner).__name__}")
        if "data" not in inner:
            raise ValueError("Missing 'data.data' array")
        if "series" not in inner:
            raise ValueError("Missing 'data.series' array")
        if not isinstance(inner["data"], list):
            raise ValueError("'data.data' must be a list")
        if len(inner["data"]) == 0:
            raise ValueError("'data.data' is empty — LLM returned no data points")
        # Validate series keys exist in data objects
        for s in inner["series"]:
            key = s.get("key") or s.get("xKey") or s.get("yKey")
            if key and key not in inner["data"][0] and key not in {"x", "y"}:
                raise ValueError(f"Series key '{key}' not found in data objects")

        display_results.append(chart_obj)
        tool_messages.append(ToolMessage(
            content="Chart filled and sent to frontend.",
            tool_call_id=tool_id,
        ))
        log.info(
            f"[DISPLAY] ✓ Chart ready — {len(chart_obj['data']['data'])} data points, "
            f"title='{chart_obj['data'].get('title')}'"
        )

    except json.JSONDecodeError as e:
        log.error(f"[DISPLAY] Invalid JSON from LLM: {e} | raw: {_truncate(raw_json, 300)}")
        tool_messages.append(ToolMessage(content="Chart failed — bad JSON.", tool_call_id=tool_id))
    except ValueError as e:
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
