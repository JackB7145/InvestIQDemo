from langgraph.graph import StateGraph, END
from state import AgentState
from nodes import (
    project_manager_node,
    researcher_node,
    display_agent_node,
    response_agent_node,
)
# =============================================================================
# ROUTING
# =============================================================================
def after_validator(state: AgentState) -> str:
    """Loop back to PM on fail, max 2 retries."""
    if state.get("evaluation") == "fail" and state.get("retry_count", 0) < 2:
        return "retry"
    return END
# =============================================================================

'''
Notes: 

1. Research should add results to thinking ("Retrieving from bigquery...", "top 5 rows of data retreived below: <Data retrieved>")
2. Graphs results should output the thinking box ("Plotting data to line graph")
3. How does bigquery -> display_agent return json -> reconstructs in frontend
4. Can you edit the graph in the frontend



'''
# =============================================================================
def build_graph():
    builder = StateGraph(AgentState)
    # Register nodes
    builder.add_node("project_manager", project_manager_node)
    builder.add_node("researcher",      researcher_node)
    builder.add_node("display_agent",   display_agent_node)
    builder.add_node("response_agent",  response_agent_node)
    # builder.add_node("validator",       validator_node)
    # Entry
    builder.set_entry_point("project_manager")
    # PM fans out to both parallel nodes
    builder.add_edge("project_manager", "researcher")
    # Both parallel nodes fan in to response_agent
    builder.add_edge("researcher",  "response_agent")
    # display_agent runs after response_agent — full context available
    builder.add_edge("response_agent", "display_agent")
    # builder.add_edge("display_agent",  "validator")
    # Validator: pass → END, fail → back to PM
    # builder.add_conditional_edges(
    #     "validator",
    #     after_validator,
    #     {
    #         "retry": "project_manager",
    #         END: END,
    #     },
    # )
    return builder.compile()
agent_graph = build_graph()