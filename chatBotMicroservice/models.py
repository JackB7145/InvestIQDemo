from langchain_ollama import ChatOllama
from httpx import Timeout as HttpxTimeout

# =============================================================================
# LLM CLIENTS
#
# Switched from qwen3 to llama3.2 — qwen3 burns all tokens on internal
# thinking with this version of Ollama, returning content=''. llama3.2 has
# no thinking mode overhead.
# =============================================================================

# Fast/tiny — thinker node (short narrative) + validator (JSON verdict)
llm_fast = ChatOllama(
    model="llama3.2:1b",
    num_ctx=1024,
    num_predict=256,
    num_thread=4,
    repeat_penalty=1.1,
    keep_alive="10m",
    client_kwargs={
        "timeout": HttpxTimeout(connect=5.0, read=30.0, write=5.0, pool=5.0)
    },
)

# Medium — PM planning + researcher planner (needs meta-awareness)
llm_medium = ChatOllama(
    model="llama3.2:3b",
    num_ctx=2048,
    num_predict=512,
    num_thread=6,
    repeat_penalty=1.15,
    temperature=0.5,
    keep_alive="10m",
    client_kwargs={
        "timeout": HttpxTimeout(connect=5.0, read=60.0, write=5.0, pool=5.0)
    },
)

# Respond — final answer + display chart fill (needs large output budget)
llm_respond = ChatOllama(
    model="llama3.2:3b",
    num_ctx=4096,       # was 3072 — more context for research + chart JSON
    num_predict=2048,   # was 1024 — needed for 28 data point chart JSON
    num_thread=6,
    repeat_penalty=1.15,
    temperature=0.7,
    keep_alive="10m",
    client_kwargs={
        "timeout": HttpxTimeout(connect=5.0, read=180.0, write=5.0, pool=5.0)  # was 90s
    },
)

llm_large = ChatOllama(
    model="llama3.2:3b",
    num_ctx=8192,       # bigger context window for large API responses
    num_predict=4096,   # allow more output tokens
    num_thread=6,
    repeat_penalty=1.15,
    temperature=0.7,
    keep_alive="10m",
)