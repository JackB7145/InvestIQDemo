import time
from langchain_core.messages import SystemMessage, HumanMessage
from state import AgentState
from models import llm_medium
from nodes.helpers import log, _sla_exceeded, _llm_text, _truncate
from nodes.prompts import PROJECT_MANAGER_PROMPT


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
            SystemMessage(content=PROJECT_MANAGER_PROMPT),
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
