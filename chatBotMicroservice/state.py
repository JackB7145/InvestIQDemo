from typing import Annotated, TypedDict, Any
from langgraph.graph.message import add_messages


def merge_lists(left: list, right: list) -> list:
    return (left or []) + (right or [])


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    stream_chunks: Annotated[list[str], merge_lists]
    display_results: Annotated[list, merge_lists]
    reasoning_summary: str
    evaluation: str
    retry_count: int
    token_queue: Any
    start_time: float           # set once in controller, checked in every node
    needs_validation: bool      # opt-in evaluator