# AI Agent Rules — LangGraph Multi-Agent Design

## Graph Design

- The graph topology lives exclusively in `graph.py`. Nodes and edges must not be
  registered anywhere else.
- All nodes must be registered before any edges are defined.
- Use `add_conditional_edges` only for routing decisions. Linear steps use `add_edge`.
- Fan-out (parallel nodes) requires that all downstream state fields use merge reducers
  in `AgentState`. Missing a reducer on a parallel-write field causes silent data loss.

## Agent Roles (current)

| Node | Responsibility |
|------|---------------|
| `project_manager` | Decomposes the user query into a plan (`pm_plan`) |
| `thinker` | Reasons about the plan; writes `think_summary` |
| `researcher` | Retrieves data / tools; writes `reasoning_summary` |
| `display_agent` | Formats output for the UI; populates `display_results` |
| `response_agent` | Produces the final user-facing message |
| `validator` | Evaluates quality; triggers retry or terminates |

**When adding a new node:**
1. Define the node function in `nodes.py`.
2. Register it in `graph.py` with `builder.add_node`.
3. Wire edges before calling `builder.compile()`.
4. Add any new state fields to `AgentState` in `state.py` with appropriate reducers.

## Prompting

- Every node that calls the LLM must have its system prompt defined as a module-level
  constant, not an inline string. This makes prompts easy to find and iterate on.
- Prompts must be deterministic in structure. Dynamic content goes in the `user` turn, not
  the `system` turn.
- Explicitly instruct the model on output format (JSON, markdown, plain text). Parse and
  validate the output before writing it to state.

## Retry Logic

- The validator controls the retry loop. Max retries = 2 (hard-coded guard in `after_validator`).
- Each retry must increment `retry_count` in state. Nodes must not reset this counter.
- On the final retry failure, the graph must reach `END` gracefully — never hang.
- Log evaluation critiques (`evaluation_critique`) even on pass, for observability.

## Ollama / LLM Calls

- Use a single shared Ollama client configuration. Do not instantiate new clients per node.
- Model name must be a constant or env var. Never hard-code model strings inside node logic.
- Handle `OllamaError` / connection errors explicitly. Surface a readable message to the
  user rather than an unhandled traceback.

## Observability

- Log the start time (`start_time`) and total elapsed time at graph exit.
- Each node should log entry and exit at `DEBUG` level.
- Errors inside nodes must be logged at `ERROR` level with full context before re-raising.

## Do Not

- Do not give a single node more than one LLM call — split it into two nodes instead.
- Do not store raw LLM output directly in `messages` unless it is an actual conversational
  turn. Use dedicated state fields for intermediate reasoning.
- Do not add tool calls inside parallel nodes (thinker/researcher) unless you have confirmed
  that LangGraph tool-node integration handles fan-out correctly for that version.
