from typing import Annotated, TypedDict, Any
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def merge_lists(left: list, right: list) -> list:
    return (left or []) + (right or [])

class AgentState(TypedDict):
    messages:            Annotated[list, add_messages]  # ← handles parallel writes
    pm_plan:             str
    stream_chunks:       Annotated[list, lambda a, b: a + b]  # ← merge lists
    display_results:     Annotated[list, lambda a, b: a + b]  # ← merge lists
    think_summary:       str
    reasoning_summary:   str
    evaluation:          str
    evaluation_critique: str
    retry_count:         int
    token_queue:         Any
    start_time:          float
    needs_validation:    bool