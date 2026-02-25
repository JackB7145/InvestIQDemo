import json
import time
import re
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from state import AgentState
from models import llm_large
from tools import TOOL_MAP
from nodes.helpers import (
    log, _sla_exceeded, _llm_text, _truncate,
    CHART_TYPE_EXTRACT,
    RESPOND_TOOL_CONTEXT_WINDOW,
    _extract_tool_context,
    extract_json_object,
)

# --------------------------
# STRICT SYSTEM PROMPT
# --------------------------
DISPLAY_FILL_PROMPT = (
    "You are a precise chart generator. STRICTLY follow these rules:\n"
    "- Output ONLY valid JSON, one object, no markdown or explanations.\n"
    "- 'data' array: one object per series. No combining series.\n"
    "- 'x' and 'y' must be flat 1D arrays of numbers.\n"
    "- 'name' must be a string describing the series.\n"
    "- 'type' must always be 'scatter' for line graphs.\n"
    "- 'mode' must be 'lines+markers'.\n"
    "- 'line.color' or 'marker.color' must be a string (hex).\n"
    "- Layout must include title, xaxis.title, yaxis.title.\n"
    "- 7–28 points per series.\n"
    "- Fill with real or illustrative numeric values. Do NOT put placeholder strings.\n"
)

# --------------------------
# GRAPH TYPE MAP
# --------------------------
_GRAPH_TYPE_MAP = {
    "scatterplot": "ScatterPlot",
    "scatter":     "ScatterPlot",
    "linegraph":   "LineGraph",
    "line":        "LineGraph",
    "bargraph":    "BarGraph",
    "bar":         "BarGraph",
    "histogram":   "BarGraph",
}

# --------------------------
# SCHEMAS (simplified + type hints)
# --------------------------
GRAPH_SCHEMAS = {
    "LineGraph": {
        "type": "LineGraph",
        "data": [
            {
                "x": "int[]",        # flat array of integers
                "y": "float[]",      # flat array of floats
                "name": "str",
                "type": "scatter",
                "mode": "lines+markers",
                "line": {"color": "str"},
            }
        ],
        "layout": {
            "title": "str",
            "xaxis": {"title": "str"},
            "yaxis": {"title": "str"},
        },
        "dynamic_traces": True,
    },
    "BarGraph": {
        "type": "BarGraph",
        "data": [
            {
                "x": "str[]",
                "y": "float[]",
                "name": "str",
                "type": "bar",
                "marker": {"color": "str"},
            }
        ],
        "layout": {
            "title": "str",
            "xaxis": {"title": "str"},
            "yaxis": {"title": "str"},
        },
        "dynamic_traces": True,
    },
    "ScatterPlot": {
        "type": "ScatterPlot",
        "data": [
            {
                "x": "float[]",
                "y": "float[]",
                "name": "str",
                "mode": "markers",
                "marker": {"color": "str"},
            }
        ],
        "layout": {
            "title": "str",
            "xaxis": {"title": "str"},
            "yaxis": {"title": "str"},
        },
        "dynamic_traces": True,
    },
}

# --------------------------
# HELPER: JSON cleanup
# --------------------------
def _clean_llm_json(raw_text: str) -> str:
    raw_text = raw_text.strip()
    try:
        raw_text = extract_json_object(raw_text)
    except Exception:
        return "{}"
    raw_text = re.sub(r'":\s*"[^"]*$', '":""', raw_text)
    raw_text = re.sub(r",(\s*[}\]])", r"\1", raw_text)
    raw_text = re.sub(r'"[^"]*"\s*:\s*(?=,|[}\]])', '', raw_text)
    raw_text = re.sub(r",\s*,", ",", raw_text)
    raw_text = re.sub(r"{\s*,", "{", raw_text)
    raw_text = re.sub(r",\s*}", "}", raw_text)
    raw_text = re.sub(r"\[\s*,", "[", raw_text)
    raw_text = re.sub(r",\s*\]", "]", raw_text)
    if not raw_text.startswith("{") or not raw_text.endswith("}"):
        return "{}"
    return raw_text

def _validate_json(raw_text: str) -> str:
    try:
        cleaned = _clean_llm_json(raw_text)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            return "{}"
        return cleaned
    except Exception:
        return "{}"

# --------------------------
# MAIN DISPLAY AGENT
# --------------------------
def display_agent_node(state: AgentState) -> AgentState:
    log.info("━━━ [DISPLAY AGENT] Determining visuals")
    t0 = time.time()
    if _sla_exceeded(state):
        return {"messages": [], "display_results": [], "stream_chunks": []}

    pm_plan = state.get("pm_plan", "")
    chart_match = CHART_TYPE_EXTRACT.search(pm_plan)
    raw_type = chart_match.group(1).strip().lower() if chart_match else "none"
    graph_type = _GRAPH_TYPE_MAP.get(raw_type)
    if not graph_type:
        return {"messages": [], "display_results": [], "stream_chunks": []}

    schema_fn = TOOL_MAP.get("get_graph_data")
    if not schema_fn:
        return {"messages": [], "display_results": [], "stream_chunks": []}

    try:
        schemas = schema_fn.invoke({"graph_type": graph_type})
        schema_template = schemas[0] if schemas else {}
    except Exception as e:
        log.error(f"Schema retrieval failed: {e}", exc_info=True)
        return {"messages": [], "display_results": [], "stream_chunks": []}

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )

    tool_context = _extract_tool_context(state["messages"])
    context_section = (
        f"Research context (use these numbers only):\n{tool_context[:RESPOND_TOOL_CONTEXT_WINDOW]}"
        if tool_context else "Research context: None. Use illustrative numeric values."
    )

    minified_schema = json.dumps(schema_template, separators=(",", ":"))

    fill_user = (
        f"User request: {user_msg[:300]}\n"
        f"{context_section}\n"
        f"Template to fill:\n{minified_schema}\n"
        f"STRICT REQUIREMENTS: Use flat 1D arrays, no placeholder strings, each series separate."
    )

    display_results = []
    tool_messages = []
    tool_id = f"tc_graph_{int(t0 * 1000)}"

    ai_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "get_graph_data",
            "args": {"graph_type": graph_type},
            "id": tool_id,
            "type": "tool_call",
        }]
    )

    try:
        fill_resp = llm_large.invoke([
            SystemMessage(content=DISPLAY_FILL_PROMPT),
            HumanMessage(content=fill_user),
        ])
        raw_text = _llm_text(fill_resp)
        print(f"Raw LLM output:\n{raw_text}\n--- End of raw output ---")

        cleaned_json = _validate_json(raw_text)
        chart_obj = json.loads(cleaned_json)

        # Enforce schema
        if "type" not in chart_obj or "data" not in chart_obj or not chart_obj["data"]:
            raise ValueError("Invalid chart object")

        display_results.append(chart_obj)
        tool_messages.append(ToolMessage(content="Chart generated successfully.", tool_call_id=tool_id))

    except Exception as e:
        tool_messages.append(ToolMessage(content=f"Chart generation failed: {e}", tool_call_id=tool_id))
        return {
            "messages": [ai_msg] + tool_messages,
            "display_results": [],
            "stream_chunks": [],
            "display_failed": True,
        }

    return {"messages": [ai_msg] + tool_messages, "display_results": display_results, "stream_chunks": []}