from typing import Annotated, TypedDict, Any
from langgraph.graph.message import add_messages


def merge_lists(left: list, right: list) -> list:
    return (left or []) + (right or [])


class AgentState(TypedDict):
    messages:            Annotated[list, add_messages]
    pm_plan:             str
    stream_chunks:       Annotated[list, merge_lists]
    display_results:     Annotated[list, merge_lists]
    data_fetched:        bool
    evaluation:          str
    evaluation_critique: str
    retry_count:         int
    token_queue:         Any
    start_time:          float
