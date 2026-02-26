import json
import time
import re
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from state import AgentState
from models import llm_large
from tools import TOOL_MAP
from nodes.helpers import (
    log, _sla_exceeded, _truncate, llm_call,
    CHART_TYPE_EXTRACT,
    RESPOND_TOOL_CONTEXT_WINDOW,
    _extract_tool_context,
    extract_json_object,
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
# CALL 1 PROMPT: Data extraction only
# --------------------------
DATA_PROCESSOR_PROMPT = (
    "You are a data extraction and organization assistant.\n"
    "Given a user request and raw research context, extract and organize the relevant data.\n"
    "Output ONLY valid JSON with this exact structure:\n"
    "{\n"
    '  "title": "string — descriptive chart title",\n'
    '  "xaxis_label": "string — x axis label",\n'
    '  "yaxis_label": "string — y axis label",\n'
    '  "series": [\n'
    "    {\n"
    '      "name": "string — series name",\n'
    '      "x": [1, 2, 3],\n'
    '      "y": [1.2, 3.4, 5.6]\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Rules:\n"
    "- x must be a flat 1D array of integers (e.g. years, indices)\n"
    "- y must be a flat 1D array of numbers, matching x in length\n"
    "- Each series gets its own object in the array\n"
    "- 7–28 points per series\n"
    "- If real data is available in context, use it. Otherwise use illustrative numeric values.\n"
    "- No placeholder strings, no nulls, no nested arrays.\n"
    "- Output ONLY the JSON object. No markdown, no explanation.\n"
)

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
# HELPER: Deterministic chart builder
# --------------------------
COLORS = [
    "#636EFA", "#EF553B", "#00CC96", "#AB63FA",
    "#FFA15A", "#19D3F3", "#FF6692", "#B6E880",
]

def _build_chart_object(graph_type: str, organized_data: dict) -> dict:
    title        = organized_data.get("title", "Chart")
    xaxis_label  = organized_data.get("xaxis_label", "X")
    yaxis_label  = organized_data.get("yaxis_label", "Y")
    series       = organized_data.get("series", [])

    if not series:
        raise ValueError("No series data found in organized data")

    layout = {
        "title": title,
        "xaxis": {"title": xaxis_label},
        "yaxis": {"title": yaxis_label},
    }

    if graph_type == "LineGraph":
        data = [
            {
                "x": s["x"], "y": s["y"],
                "name": s.get("name", f"Series {i + 1}"),
                "type": "scatter", "mode": "lines+markers",
                "line": {"color": COLORS[i % len(COLORS)]},
            }
            for i, s in enumerate(series)
        ]
    elif graph_type == "BarGraph":
        data = [
            {
                "x": [str(v) for v in s["x"]], "y": s["y"],
                "name": s.get("name", f"Series {i + 1}"),
                "type": "bar",
                "marker": {"color": COLORS[i % len(COLORS)]},
            }
            for i, s in enumerate(series)
        ]
    elif graph_type == "ScatterPlot":
        data = [
            {
                "x": s["x"], "y": s["y"],
                "name": s.get("name", f"Series {i + 1}"),
                "mode": "markers",
                "marker": {"color": COLORS[i % len(COLORS)]},
            }
            for i, s in enumerate(series)
        ]
    else:
        raise ValueError(f"Unknown graph type: {graph_type}")

    return {"type": graph_type, "data": data, "layout": layout}


# --------------------------
# MAIN DISPLAY AGENT
# --------------------------
def display_agent_node(state: AgentState) -> AgentState:
    log.info("━━━ [DISPLAY AGENT] Determining visuals")
    t0 = time.time()

    if _sla_exceeded(state):
        return {"messages": [], "display_results": [], "stream_chunks": []}

    # ── Determine graph type from PM plan ─────────────────────────────────────
    pm_plan     = state.get("pm_plan", "")
    chart_match = CHART_TYPE_EXTRACT.search(pm_plan)
    raw_type    = chart_match.group(1).strip().lower() if chart_match else "none"
    graph_type  = _GRAPH_TYPE_MAP.get(raw_type)

    if not graph_type:
        return {"messages": [], "display_results": [], "stream_chunks": []}

    user_msg     = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )
    tool_context = _extract_tool_context(state["messages"])
    context_section = (
        f"Research context (use these numbers only):\n{tool_context[:RESPOND_TOOL_CONTEXT_WINDOW]}"
        if tool_context else "Research context: None. Use illustrative numeric values."
    )

    tool_id = f"tc_graph_{int(t0 * 1000)}"
    ai_msg  = AIMessage(
        content="",
        tool_calls=[{
            "name": "get_graph_data",
            "args": {"graph_type": graph_type},
            "id": tool_id,
            "type": "tool_call",
        }]
    )

    def _fail(reason: str) -> AgentState:
        log.error(f"[DISPLAY] {reason}")
        return {
            "messages": [ai_msg, ToolMessage(content=reason, tool_call_id=tool_id)],
            "display_results": [],
            "stream_chunks":   [],
            "display_failed":  True,
        }

    # ── CALL 1: Extract & organize data via intermediary ──────────────────────
    data_user_msg = (
        f"User request: {user_msg[:300]}\n"
        f"{context_section}\n"
        f"Graph type: {graph_type}\n"
        "Extract and organize the data needed for this chart."
    )

    raw_data_text = llm_call(
        state,
        llm_large.invoke,
        [
            SystemMessage(content=DATA_PROCESSOR_PROMPT),
            HumanMessage(content=data_user_msg),
        ],
        status_before="📊 Extracting chart data…",
        status_after="✅ Data extracted",
        label="DISPLAY-data",
    )

    if not raw_data_text:
        return _fail("Data processing call returned empty response")

    log.debug(f"[DISPLAY] Raw data output: {_truncate(raw_data_text, 200)}")

    try:
        clean_json     = _validate_json(raw_data_text)
        organized_data = json.loads(clean_json)
        if "series" not in organized_data or not organized_data["series"]:
            raise ValueError("No series data in response")
    except Exception as e:
        return _fail(f"Data processing failed: {e}")

    # ── Build chart object deterministically ──────────────────────────────────
    try:
        chart_obj = _build_chart_object(graph_type, organized_data)
    except Exception as e:
        return _fail(f"Chart building failed: {e}")

    log.info(f"[DISPLAY] ✓ Done in {time.time() - t0:.2f}s")

    tool_msg = ToolMessage(content="Chart generated successfully.", tool_call_id=tool_id)
    return {
        "messages":       [ai_msg, tool_msg],
        "display_results": [chart_obj],
        "stream_chunks":   [],
    }