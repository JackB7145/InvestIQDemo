import json
import re
import time
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import AgentState
from models import llm_fast
from nodes.helpers import (
    log, _llm_text,
    GRAPH_SLA_SECS,
    VALIDATOR_QUESTION_WINDOW,
    VALIDATOR_RESPONSE_WINDOW,
)
from nodes.prompts import VALIDATOR_PROMPT


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
            SystemMessage(content=VALIDATOR_PROMPT),
            HumanMessage(content=(
                f"User question: {user_msg[:VALIDATOR_QUESTION_WINDOW]}\n\n"
                f"Response to validate:\n{last_response[:VALIDATOR_RESPONSE_WINDOW]}"
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
        log.warning(f"[VALIDATOR] JSON parse failed: {e} — defaulting to fail")
        result = "fail"
        critique = "Validator could not parse LLM output."
    except Exception as e:
        log.warning(f"[VALIDATOR] LLM check failed: {e} — defaulting to fail")
        result = "fail"
        critique = "Validator LLM call failed."

    new_retry = retry_count + (1 if result == "fail" else 0)
    log.info(
        f"[VALIDATOR] ✓ {result.upper()} | '{critique}' | "
        f"{time.time()-t0:.2f}s | retries: {retry_count} → {new_retry}"
    )

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
