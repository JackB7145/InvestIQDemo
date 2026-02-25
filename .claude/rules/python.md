# Python Rules — FastAPI & LangGraph

## Dependency Management

- Pin all dependencies in `requirements.txt` with exact versions (`==`), not ranges.
- Use a virtual environment. Never install packages globally.
- After adding a package, immediately update `requirements.txt`:
  ```bash
  pip freeze > requirements.txt
  ```

## FastAPI

- **Always** declare request/response models with Pydantic. Never use raw `dict`.
  ```python
  # GOOD
  class ChatRequest(BaseModel):
      prompt: str

  # BAD
  async def chat(body: dict): ...
  ```
- **Keep routers thin.** Business logic belongs in service/graph layers, not in route handlers.
- **CORS** is locked to `http://localhost:3000` in dev. Do not open to `*` without a deliberate, reviewed change.
- Use `async def` for all route handlers that call async code (LangGraph, streaming).
- Return structured errors with appropriate HTTP status codes, not bare 500s.

## Streaming

- Stream tokens directly from LangGraph nodes using `asyncio.Queue` or `token_queue` in `AgentState`.
- Do **not** accumulate the full response before sending — this defeats the purpose of streaming.
- Always set `Content-Type: text/plain; charset=utf-8` and flush headers immediately.

## LangGraph & State

- `AgentState` is the single source of truth. All node inputs and outputs go through it.
- Use `Annotated` reducers for fields that can be written by parallel nodes (fan-out):
  ```python
  stream_chunks: Annotated[list, lambda a, b: a + b]
  ```
- Never mutate shared mutable state inside a node. Return a new partial state dict.
- Keep node functions pure where possible — side effects (logging, DB writes) should be
  explicit and isolated.

## Node Design

- One responsibility per node. A node that both reasons AND formats output is two nodes.
- Name nodes as `<role>_node` (e.g., `thinker_node`, `validator_node`).
- Validate required state keys at the top of each node and raise early with a clear message.
- The validator node must enforce a **maximum retry count** (`retry_count < 2`) to prevent infinite loops.

## Code Style

- Follow PEP 8. Max line length: 100 characters.
- Type-hint all function signatures.
- Use docstrings for non-trivial functions and all public APIs.
- Prefer explicit imports over wildcard (`from module import *`).
- Group imports: stdlib → third-party → local, separated by blank lines.
