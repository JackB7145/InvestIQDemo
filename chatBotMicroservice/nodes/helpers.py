import json
import logging
import time
import re
from langchain_core.messages import ToolMessage

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
# CONSTANTS — Graph-level limits
# =============================================================================

GRAPH_SLA_SECS          = 180   # hard timeout for the whole graph
MAX_PROMPT_CHARS        = 4000  # max chars of a tool result stored in state
MAX_MESSAGES            = 6     # max conversation turns kept
RESEARCHER_MAX_ITERATIONS = 3   # max tool-call iterations per request

# =============================================================================
# CONSTANTS — LLM window sizes (chars sent to each node)
# =============================================================================

RESEARCHER_QUESTION_WINDOW  = 300   # user question shown to planner
RESEARCHER_NEED_WINDOW      = 200   # data_needed excerpt shown to planner
RESEARCHER_CONTEXT_WINDOW   = 600   # accumulated results shown to planner
RESPOND_TOOL_CONTEXT_WINDOW = 1500  # tool context passed to response agent
RESPOND_PM_PLAN_WINDOW      = 400   # pm_plan excerpt appended to user turn
VALIDATOR_QUESTION_WINDOW   = 200   # user question shown to validator
VALIDATOR_RESPONSE_WINDOW   = 600   # response excerpt shown to validator
LOG_CHUNK_PREVIEW           = 80    # chars of a chunk logged in controller

# =============================================================================
# REGEX PATTERNS
# =============================================================================

# Allow for markdown bold formatting the PM model sometimes emits, e.g.
# "**DATA_NEEDED:** none" or "**CHART_TYPE**: BarGraph"
DATA_NEEDED_EXTRACT = re.compile(r"DATA_NEEDED\s*\*{0,2}\s*:\s*\*{0,2}\s*(.+?)(?:\n|$)", re.I)
CHART_TYPE_EXTRACT  = re.compile(r"CHART_TYPE\s*\*{0,2}\s*:\s*\*{0,2}\s*(\w+)", re.I)

# =============================================================================
# HELPERS
# =============================================================================

def emit(type: str, data) -> str:
    return json.dumps({"type": type, "data": data}) + "\n"


def extract_json_object(text: str) -> str:
    """Return the first complete {...} JSON object from text.

    Handles cases where the LLM adds explanation text before or after the JSON,
    or produces pretty-printed JSON that is then truncated.
    """
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    # Truncated — return whatever we captured
    return text[start:]


def _truncate(text: str, max: int = 120) -> str:
    text = str(text)
    return text if len(text) <= max else text[:max] + "..."


def _sla_exceeded(state) -> bool:
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


def _llm_text(resp) -> str:
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
