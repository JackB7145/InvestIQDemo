from langgraph.graph import StateGraph, END
from state import AgentState
from nodes import (
    reason_node,
    plan_tools_node,
    tool_node,
    respond_node,
    display_decision_node,
    merge_parallel_node,
    evaluator_node,
)
from langchain_core.messages import AIMessage


def should_use_tools(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage):
            if getattr(msg, "tool_calls", []):
                return "tools"
            return "merge_2"
    return "merge_2"

def after_evaluation(state: AgentState) -> str:
    if state.get("evaluation") == "fail" and state.get("retry_count", 0) < 2:
        return "retry"
    return END


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("reason", reason_node)
    builder.add_node("plan_tools", plan_tools_node)
    builder.add_node("tools", tool_node)
    builder.add_node("merge_2", merge_parallel_node)
    builder.add_node("respond", respond_node)
    builder.add_node("display_decision", display_decision_node)
    builder.add_node("merge_3", merge_parallel_node)
    builder.add_node("evaluator", evaluator_node)

    builder.set_entry_point("reason")

    # reason → plan_tools (no more parallel summarize branch)
    builder.add_edge("reason", "plan_tools")

    builder.add_conditional_edges("plan_tools", should_use_tools, {
        "tools": "tools",
        "merge_2": "merge_2",
    })
    builder.add_edge("tools", "merge_2")
    builder.add_edge("merge_2", "respond")
    builder.add_edge("merge_2", "display_decision")
    builder.add_edge("respond", "merge_3")
    builder.add_edge("display_decision", "merge_3")
    builder.add_edge("merge_3", "evaluator")

    builder.add_conditional_edges("evaluator", after_evaluation, {
        "retry": "reason",
        END: END,
    })

    return builder.compile()

agent_graph = build_graph()