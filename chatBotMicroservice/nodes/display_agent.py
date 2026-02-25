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


def _clean_llm_json(raw_text: str) -> str:
    """
    Aggressively clean LLM JSON output:
    - Keep only the first JSON object.
    - Remove trailing commas and empty/malformed entries.
    - Remove unterminated strings or broken objects entirely.
    - Returns valid JSON string or '{}' if nothing safe remains.
    """
    raw_text = raw_text.strip()

    # Extract first JSON object
    try:
        raw_text = extract_json_object(raw_text)
    except Exception:
        return "{}"

    # Remove dangling or incomplete strings (quotes not closed)
    raw_text = re.sub(r'":\s*"[^"]*$', '":""', raw_text)

    # Remove trailing commas before closing braces/brackets
    raw_text = re.sub(r",(\s*[}\]])", r"\1", raw_text)

    # Remove entries with empty keys like "":123
    raw_text = re.sub(r'"[^"]*"\s*:\s*(?=,|[}\]])', '', raw_text)

    # Remove consecutive commas
    raw_text = re.sub(r",\s*,", ",", raw_text)

    # Remove dangling commas inside braces/brackets
    raw_text = re.sub(r"{\s*,", "{", raw_text)
    raw_text = re.sub(r",\s*}", "}", raw_text)
    raw_text = re.sub(r"\[\s*,", "[", raw_text)
    raw_text = re.sub(r",\s*\]", "]", raw_text)

    # Fallback if not a JSON object
    if not raw_text.startswith("{") or not raw_text.endswith("}"):
        return "{}"

    return raw_text


def _validate_json(raw_text: str) -> str:
    """
    Parse cleaned JSON safely and ensure top-level object.
    Returns '{}' if invalid.
    """
    try:
        cleaned = _clean_llm_json(raw_text)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            return "{}"
        return cleaned
    except Exception:
        return "{}"


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

    schema_fn = TOOL_MAP.get("get_graph_data")
    if not schema_fn:
        log.error("[DISPLAY] No handler for graph schema provider")
        return {"messages": [], "display_results": [], "stream_chunks": []}

    try:
        schemas = schema_fn.invoke({"graph_type": graph_type})
        schema_template = schemas[0] if schemas else {}
        log.info(f"[DISPLAY] Got schema template for {graph_type}")
    except Exception as e:
        log.error(f"[DISPLAY] Schema retrieval failed: {e}", exc_info=True)
        return {"messages": [], "display_results": [], "stream_chunks": []}

    user_msg = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
    )

    tool_context = _extract_tool_context(state["messages"])
    if tool_context:
        context_section = (
            f"Research context (use these numbers only):\n"
            f"{tool_context[:RESPOND_TOOL_CONTEXT_WINDOW]}"
        )
        data_instruction = "Use ONLY numeric values from the research context."
    else:
        context_section = (
            "Research context: None available. "
            "Use realistic illustrative values."
        )
        data_instruction = "Use plausible illustrative values."

    minified_schema = json.dumps(schema_template, separators=(",", ":"))

    fill_user = (
        f"User request: {user_msg[:300]}\n\n"
        f"{context_section}\n\n"
        f"Template to fill:\n{minified_schema}\n\n"
        f"{data_instruction}\n\n"
        "STRICT REQUIREMENTS:\n"
        "- Return ONLY valid JSON.\n"
        "- No markdown, explanations, or trailing commas.\n"
        "- 8–12 data points max.\n"
        "- Response MUST begin with { and end with }.\n"
        "- Maintain exact schema structure.\n"
        "- Generate meaningful 'name' fields and axis/series labels."
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
        log.info(f"[DISPLAY] LLM cleaned output: {_truncate(cleaned_json, 300)}")

        chart_obj = json.loads(cleaned_json)

        # ✅ Strict schema enforcement
        if "type" not in chart_obj:
            raise ValueError("Missing 'type'")
        if "data" not in chart_obj or not isinstance(chart_obj["data"], list):
            raise ValueError("Invalid or missing 'data' object")

        if not chart_obj["data"]:
            raise ValueError("No data points returned")

        display_results.append(chart_obj)

        tool_messages.append(ToolMessage(
            content="Chart generated successfully.",
            tool_call_id=tool_id,
        ))

        log.info(
            f"[DISPLAY] ✓ Chart ready — {len(chart_obj['data'])} points | "
            f"title='{chart_obj.get('layout', {}).get('title')}'"
        )

    except Exception as e:
        log.error(f"[DISPLAY] Chart generation failed: {e}", exc_info=True)

        tool_messages.append(ToolMessage(
            content=f"Chart generation failed: {str(e)}",
            tool_call_id=tool_id,
        ))

        return {
            "messages": [ai_msg] + tool_messages,
            "display_results": [],
            "stream_chunks": [],
            "display_failed": True,
        }

    log.info(f"[DISPLAY] ✓ Done in {time.time() - t0:.2f}s | {len(display_results)} chart(s)")

    return {
        "messages": [ai_msg] + tool_messages,
        "display_results": display_results,
        "stream_chunks": [],
    }