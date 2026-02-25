# InvestIQ — Improvement Guide

Every issue found in the codebase, explained in plain language with the exact problem and how to fix it.

---

## Table of Contents

1. [CRITICAL — API Key Hardcoded in Source](#1-api-key-hardcoded-in-source)
2. [CRITICAL — Backend URL Hardcoded in Frontend](#2-backend-url-hardcoded-in-frontend)
3. [CRITICAL — Thread/Queue Race Condition in Streaming](#3-threadqueue-race-condition-in-streaming)
4. [CRITICAL — None Crashes the State Merge](#4-none-crashes-the-state-merge)
5. [HIGH — No Input Validation on the Chat Endpoint](#5-no-input-validation-on-the-chat-endpoint)
6. [HIGH — botSeeded Flag Never Resets](#6-botseeded-flag-never-resets)
7. [HIGH — Sufficiency Check Defaults to SUFFICIENT on Failure](#7-sufficiency-check-defaults-to-sufficient-on-failure)
8. [HIGH — splitlines()[0] Has No Bounds Check](#8-splitlines0-has-no-bounds-check)
9. [HIGH — controller.py Returns a Tuple, Not a Proper Error Response](#9-controllerpy-returns-a-tuple-not-a-proper-error-response)
10. [MEDIUM — nodes.py Is 760 Lines — One File Doing Everything](#10-nodesty-is-760-lines--one-file-doing-everything)
11. [MEDIUM — Stream Parsing Logic Lives Inside the Component](#11-stream-parsing-logic-lives-inside-the-component)
12. [MEDIUM — Two LLM Calls Per Researcher Loop Iteration](#12-two-llm-calls-per-researcher-loop-iteration)
13. [MEDIUM — String Joined Every Loop Iteration](#13-string-joined-every-loop-iteration)
14. [MEDIUM — Duplicate TypedDict Import](#14-duplicate-typeddict-import)
15. [MEDIUM — Unused State Fields in AgentState](#15-unused-state-fields-in-agentstate)
16. [MEDIUM — Dead Code: dummyData.py and toolsResponse](#16-dead-code-dummydatapy-and-toolsresponse)
17. [MEDIUM — "SUFFICIENT" in verdict Is Too Loose](#17-sufficient-in-verdict-is-too-loose)
18. [MEDIUM — merge_lists() Defined But Not Used](#18-merge_lists-defined-but-not-used)
19. [MEDIUM — any Everywhere in TypeScript](#19-any-everywhere-in-typescript)
20. [MEDIUM — No Fetch Timeout or Abort on Component Unmount](#20-no-fetch-timeout-or-abort-on-component-unmount)
21. [MEDIUM — No Error or Loading State in the UI](#21-no-error-or-loading-state-in-the-ui)
22. [MEDIUM — Assertions Used for Control Flow in display_agent](#22-assertions-used-for-control-flow-in-display_agent)
23. [MEDIUM — System Prompts Buried Inside Node Functions](#23-system-prompts-buried-inside-node-functions)
24. [LOW — No Tests Anywhere](#24-no-tests-anywhere)
25. [LOW — Magic Numbers Throughout](#25-magic-numbers-throughout)
26. [LOW — Thread-Based Streaming Doesn't Scale](#26-thread-based-streaming-doesnt-scale)
27. [LOW — Blocking thread.join() After Streaming Is Done](#27-blocking-threadjoin-after-streaming-is-done)
28. [LOW — Validator Auto-Passes When It Fails Itself](#28-validator-auto-passes-when-it-fails-itself)
29. [LOW — No Rate Limiting on the Chat Endpoint](#29-no-rate-limiting-on-the-chat-endpoint)
30. [LOW — "Connected" Status Is Always Green](#30-connected-status-is-always-green)

---

## 1. API Key Hardcoded in Source

**File:** `chatBotMicroservice/tools.py:5`

### Problem

The Alpha Vantage API key is written directly in the source code:

```python
ALPHAVANTAGE_API_KEY = "IX51KIV6OI7GWOQD"
```

Anyone who can read this file — teammates, GitHub visitors, anyone who clones the repo — can see and use this key. If this key gets abused (rate-limited, banned, or racked up charges), you have no way to rotate it without pushing a new commit. This is one of the most common causes of leaked credentials in open source projects.

### Answer

Move it to a `.env` file that is never committed to git:

**`.env` (create this file, never commit it)**
```
ALPHAVANTAGE_API_KEY=IX51KIV6OI7GWOQD
```

**`chatBotMicroservice/.gitignore`** — add:
```
.env
```

**`tools.py`** — load it from the environment:
```python
import os
from dotenv import load_dotenv

load_dotenv()
ALPHAVANTAGE_API_KEY = os.environ["ALPHAVANTAGE_API_KEY"]
```

Install `python-dotenv` and add it to `requirements.txt`. Using `os.environ["KEY"]` (not `.get()`) means the app will fail loudly at startup if the key is missing, rather than silently sending empty requests to the API.

---

## 2. Backend URL Hardcoded in Frontend

**File:** `investiqdemo/app/api/chat/route.ts:14`

### Problem

```ts
const pythonRes = await fetch("http://localhost:8000/chat", { ... });
```

This works fine on your machine. The moment anyone deploys this app — staging, production, another developer's machine with a different port — this breaks. There is no way to change the URL without editing the source code.

### Answer

Use an environment variable:

**`.env.local` (in `investiqdemo/`, never commit)**
```
PYTHON_API_URL=http://localhost:8000
```

**`route.ts`**
```ts
const apiUrl = process.env.PYTHON_API_URL ?? "http://localhost:8000";
const pythonRes = await fetch(`${apiUrl}/chat`, { ... });
```

Next.js automatically reads `.env.local` in development. In production, set `PYTHON_API_URL` in your hosting environment. Now the URL is configurable without touching code.

---

## 3. Thread/Queue Race Condition in Streaming

**File:** `chatBotMicroservice/controller.py:87-118`

### Problem

The streaming architecture uses a background thread + a queue. There is a subtle race condition:

```python
finally:
    token_queue.put("__graph_done__")  # line 88
```

The `__graph_done__` sentinel is placed in the queue inside a `finally` block. This fires as soon as the `for event in agent_graph.stream(...)` loop exits **or raises an exception**. But `final_chunks` is still being appended to in that same loop — and on error, it might not be fully populated yet. The consumer loop breaks on `__graph_done__` and then yields `final_chunks`. If the graph errored out mid-way, `final_chunks` may be empty or incomplete.

There is also this at the very end:

```python
thread.join()  # line 118
```

This `join()` is called **after** the generator has already yielded everything. The HTTP response is already closed at this point. Joining the thread here is pointless — the thread is done or the call blocks forever if something went wrong. It provides no value and is a latent hang risk.

### Answer

Simplify the signal: put `__graph_done__` only after the graph finishes successfully, and put an error sentinel on exception. Remove the `thread.join()` call entirely since the thread is `daemon=True` and will clean itself up.

```python
def run_graph():
    try:
        for event in agent_graph.stream(initial_state, stream_mode="updates"):
            for node_name, node_state in event.items():
                for chunk in node_state.get("stream_chunks", []):
                    try:
                        chunk_type = json.loads(chunk).get("type", "")
                    except Exception:
                        chunk_type = ""
                    if chunk_type != "thinking_content":
                        final_chunks.append(chunk)
    except Exception as e:
        log.error(f"[GRAPH] Error: {e}")
        final_chunks.append(
            json.dumps({"type": "response_content",
                        "data": "Something went wrong. Please try again."}) + "\n"
        )
    finally:
        token_queue.put("__graph_done__")  # always signals completion

thread = threading.Thread(target=run_graph, daemon=True)
thread.start()

while True:
    item = token_queue.get()
    if item == "__graph_done__":
        break
    if item != "__thinking_done__":
        yield item

# Now safe to flush — graph is confirmed done
for chunk in sorted(final_chunks, key=lambda c: TYPE_ORDER.get(..., 99)):
    yield chunk
# No thread.join() needed — daemon thread exits on its own
```

---

## 4. None Crashes the State Merge

**File:** `chatBotMicroservice/state.py:12-13`

### Problem

```python
stream_chunks:   Annotated[list, lambda a, b: a + b]
display_results: Annotated[list, lambda a, b: a + b]
```

These reducers run when LangGraph merges state from parallel nodes (thinker and researcher both run at the same time). If either node returns `None` for one of these fields instead of an empty list, the merge crashes at runtime:

```
TypeError: can only concatenate list (not "NoneType") to list
```

This can happen silently when a node returns early on an SLA check — for example, `thinker_node` at line 163 of `nodes.py` returns `{"messages": [], "stream_chunks": []}`, which is fine. But if a future change returns `None` (easy to do by accident), the whole graph crashes.

There is already a function in the same file that handles this correctly:

```python
def merge_lists(left: list, right: list) -> list:
    return (left or []) + (right or [])
```

It just isn't being used.

### Answer

Use `merge_lists` for every list field that gets written by parallel nodes:

```python
class AgentState(TypedDict):
    messages:        Annotated[list, add_messages]
    stream_chunks:   Annotated[list, merge_lists]   # was: lambda a, b: a + b
    display_results: Annotated[list, merge_lists]   # was: lambda a, b: a + b
    ...
```

---

## 5. No Input Validation on the Chat Endpoint

**File:** `chatBotMicroservice/controller.py:33-35`

### Problem

```python
@router.post("/chat")
def chat(req: ChatRequest):
    if not req.prompt.strip():
        return {"error": "Prompt is required"}, 400
```

The only check is whether the prompt is empty. There is no:
- Maximum length limit — a user could send a 100,000 character string and it gets passed directly to the LLM, consuming your context window and burning time
- Character validation — no guard against weird control characters or injection patterns
- Rate limiting — the same IP can hammer `/chat` continuously, running multiple full graph executions in parallel

### Answer

Add a length cap at minimum:

```python
MAX_PROMPT_LENGTH = 2000

@router.post("/chat")
def chat(req: ChatRequest):
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Prompt too long. Maximum is {MAX_PROMPT_LENGTH} characters."
        )
```

Note: also switch from `return dict, 400` (non-standard FastAPI) to `raise HTTPException`. The tuple return style is a Flask pattern — FastAPI ignores the status code in a plain tuple return and always sends 200.

---

## 6. botSeeded Flag Never Resets

**File:** `investiqdemo/app/page.tsx:60`

### Problem

```ts
let botSeeded = false;
```

`botSeeded` controls the moment the "thinking" bubble converts into a "bot" message bubble. It's set to `true` on the first `response_content` chunk and never reset. This variable lives inside `handleSubmit`, so it is re-created fresh each time the function runs — that part is fine.

The real problem is the **thinking bubble itself**. When the user submits, a thinking bubble is appended:

```ts
setChatMessages((prev) => [
    ...prev,
    { text: prompt, type: "user" },
    { text: "", type: "thinking" },   // seeded here
]);
```

If the request fails before any `response_content` chunk arrives, `botSeeded` stays `false` and the thinking bubble is never converted. The conversation ends with a dangling animated "Reasoning" bubble in the chat, permanently, because `setChatMessages` in the `catch` block appends a new error message but does **not** remove the orphaned thinking bubble.

### Answer

In the `catch` block, replace the last message (which is the orphaned thinking bubble) instead of appending a new one:

```ts
} catch (error) {
    console.error("Chat API error:", error);
    setChatMessages((prev) => {
        const updated = [...prev];
        // Replace the thinking bubble with the error message
        updated[updated.length - 1] = {
            text: "Something went wrong. Please try again.",
            type: "bot",
        };
        return updated;
    });
}
```

---

## 7. Sufficiency Check Defaults to SUFFICIENT on Failure

**File:** `chatBotMicroservice/nodes.py:392-394`

### Problem

```python
except Exception as e:
    log.warning(f"[RESEARCHER] Sufficiency check failed: {e} — assuming SUFFICIENT")
    verdict = "SUFFICIENT"
```

When the LLM call that decides "do we have enough data?" fails, the code assumes we do have enough data and stops the research loop. This is backwards. If we can't determine sufficiency, the safest assumption is that we are **not** done yet and should try another tool call. Defaulting to SUFFICIENT means a network blip or model timeout causes the researcher to stop early and hand off incomplete data to the response agent, which then produces a weak or empty answer.

### Answer

Default to INSUFFICIENT so the loop continues:

```python
except Exception as e:
    log.warning(f"[RESEARCHER] Sufficiency check failed: {e} — assuming INSUFFICIENT")
    verdict = "INSUFFICIENT"
```

The loop still has a hard cap (`RESEARCHER_MAX_ITERATIONS = 3`), so this cannot loop forever.

---

## 8. splitlines()[0] Has No Bounds Check

**File:** `chatBotMicroservice/nodes.py:310`

### Problem

```python
decision = _llm_text(planner_resp).strip().splitlines()[0].strip()
```

If `_llm_text(planner_resp)` returns an empty string, `.strip()` returns `""`, and `"".splitlines()` returns `[]`. Indexing `[][0]` raises an `IndexError`, crashing the entire researcher node. This can happen when Ollama returns an empty response — something that is already handled defensively elsewhere in the code.

### Answer

Check the list is non-empty before indexing:

```python
lines = _llm_text(planner_resp).strip().splitlines()
if not lines:
    log.warning("[RESEARCHER] Planner returned empty response — stopping")
    break
decision = lines[0].strip()
```

---

## 9. controller.py Returns a Tuple, Not a Proper Error Response

**File:** `chatBotMicroservice/controller.py:34-35`

### Problem

```python
if not req.prompt.strip():
    return {"error": "Prompt is required"}, 400
```

This is a Flask/Django pattern. In FastAPI, returning a `(dict, int)` tuple from a route handler does **not** set the HTTP status code to 400. FastAPI serialises the tuple as a JSON array — `[{"error": "Prompt is required"}, 400]` — and returns it with a **200 OK** status. The caller has no way to know an error occurred.

### Answer

Use `HTTPException`, which is FastAPI's standard error mechanism:

```python
from fastapi import HTTPException

if not req.prompt.strip():
    raise HTTPException(status_code=400, detail="Prompt is required.")
```

---

## 10. nodes.py Is 760 Lines — One File Doing Everything

**File:** `chatBotMicroservice/nodes.py`

### Problem

All five agent node implementations live in one 760-line file. When you need to change how the researcher works, you have to scroll past 400 lines of unrelated code. When a bug appears, it's hard to tell which node caused it without reading everything. The file will only grow as features are added.

### Answer

Split into one file per node. The `graph.py` import line changes but nothing else:

```
chatBotMicroservice/
  nodes/
    __init__.py
    project_manager.py
    thinker.py
    researcher.py
    display_agent.py
    response_agent.py
    validator.py
    helpers.py          ← emit(), _llm_text(), _truncate(), _sla_exceeded(), constants
```

**`nodes/__init__.py`**
```python
from .project_manager import project_manager_node
from .thinker import thinker_node
from .researcher import researcher_node
from .display_agent import display_agent_node
from .response_agent import response_agent_node
from .validator import validator_node
```

**`graph.py`** import stays the same:
```python
from nodes import (project_manager_node, thinker_node, ...)
```

---

## 11. Stream Parsing Logic Lives Inside the Component

**File:** `investiqdemo/app/page.tsx:64-148`

### Problem

`handleSubmit` in `page.tsx` contains ~90 lines of streaming logic: reading from a `ReadableStream`, buffering incomplete lines, parsing NDJSON, routing chunk types, updating state. This is not UI logic — it's a protocol parser. It's hard to test in isolation and it makes `page.tsx` hard to read.

### Answer

Extract it into a custom hook: `app/hooks/useStreamParser.ts`

```ts
// app/hooks/useStreamParser.ts
export function useStreamParser(onThinking, onResponse, onDisplay) {
    return async (response: Response) => {
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let lineBuffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            lineBuffer += decoder.decode(value, { stream: true });
            const lines = lineBuffer.split("\n");
            lineBuffer = lines.pop() ?? "";
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const parsed = JSON.parse(line);
                    if (parsed.type === "thinking_content") onThinking(parsed.data);
                    else if (parsed.type === "response_content") onResponse(parsed.data);
                    else if (parsed.type === "display_modules") onDisplay(parsed.data);
                } catch {
                    console.warn("Failed to parse chunk:", line);
                }
            }
        }
    };
}
```

`page.tsx` then becomes:

```ts
const parse = useStreamParser(onThinking, onResponse, onDisplay);
const response = await fetch("/api/chat", { ... });
await parse(response);
```

Clean, testable, and the component only handles UI state.

---

## 12. Two LLM Calls Per Researcher Loop Iteration

**File:** `chatBotMicroservice/nodes.py:306, 385`

### Problem

Every iteration of the researcher loop makes two separate calls to Ollama:

1. **Planner call** (line 306) — decides which tool to call next
2. **Sufficiency check** (line 385) — decides if we have enough data

That means for a 2-iteration research loop, you are making 4 LLM round-trips just for decision-making, before any tool results are even used in the final response. Each Ollama call has network and compute overhead, making the research phase take roughly twice as long as it needs to.

### Answer

Combine them into a single call. Ask the planner to output both the next action and a sufficiency verdict in one response:

```
Either:
  CALL: get_stock_data | {"symbol": "AAPL", "function": "OVERVIEW"}
Or if data is complete:
  DONE
```

`DONE` already serves as "SUFFICIENT" — you don't need a second LLM to confirm what the first LLM just decided. Remove the sufficiency check call entirely and rely on the planner's `DONE` signal.

---

## 13. String Joined Every Loop Iteration

**File:** `chatBotMicroservice/nodes.py:282`

### Problem

```python
context_so_far = "\n---\n".join(collected_results) if collected_results else "NO TOOLS CALLED YET..."
```

This line is inside the `while` loop. Every iteration, Python allocates a new string by joining all previously collected results. On iteration 1 it joins 0 strings. On iteration 2 it joins 1. On iteration 3 it joins 2. For small lists this doesn't matter, but it is wasteful — especially since `collected_results` could contain large API responses.

### Answer

This is a minor point but easy to fix. The join only needs to happen once per iteration, and the results don't change mid-iteration. The current code is actually already doing this (one join per loop pass), but labelling it clearly avoids future mistakes:

```python
# Build context string from all results fetched so far
context_so_far = (
    "\n---\n".join(collected_results)
    if collected_results
    else "NO TOOLS CALLED YET — you must make a CALL"
)
```

The bigger win is truncating each result as it is collected rather than truncating the joined string, which can cut off data from early results if later results are large.

---

## 14. Duplicate TypedDict Import

**File:** `chatBotMicroservice/state.py:1-3`

### Problem

```python
from typing import Annotated, TypedDict, Any
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict      # ← imports TypedDict a second time
```

`TypedDict` is imported twice. The second import shadows the first. In Python 3.8+, `TypedDict` is available directly from `typing` — the `typing_extensions` version is only needed for older Python. This is dead code that makes the imports confusing.

### Answer

Remove the duplicate:

```python
from typing import Annotated, TypedDict, Any
from langgraph.graph.message import add_messages
```

---

## 15. Unused State Fields in AgentState

**File:** `chatBotMicroservice/state.py:14-16`

### Problem

```python
think_summary:       str
reasoning_summary:   str
needs_validation:    bool
```

These three fields are declared in `AgentState` but are never written or read anywhere in `nodes.py` or `controller.py`. They appear to be leftovers from an earlier design. They add noise to the state definition and make it harder to understand what the graph actually does.

### Answer

Remove them. If they are needed later, they can be added back with a clear purpose. Unused fields in a `TypedDict` are silent — they don't cause errors, which is exactly why they are dangerous: they look intentional.

```python
class AgentState(TypedDict):
    messages:            Annotated[list, add_messages]
    pm_plan:             str
    stream_chunks:       Annotated[list, merge_lists]
    display_results:     Annotated[list, merge_lists]
    evaluation:          str
    evaluation_critique: str
    retry_count:         int
    token_queue:         Any
    start_time:          float
    data_fetched:        bool
```

---

## 16. Dead Code: dummyData.py and toolsResponse

**Files:** `chatBotMicroservice/dummyData.py`, `investiqdemo/app/api/chat/dummyGraphs.ts`

### Problem

`dummyData.py` contains Python data structures that are never imported or referenced anywhere in the backend. Similarly, `dummyGraphs.ts` exports a `toolsResponse` object that is never imported by any frontend file. Dead code creates confusion: a new developer reading the project will wonder what these are for, whether they are needed, and whether removing them will break something.

### Answer

Delete both files. If they were used for manual testing, that testing should be replaced with actual test files (see issue #24). Keep code that runs, remove code that doesn't.

---

## 17. "SUFFICIENT" in verdict Is Too Loose

**File:** `chatBotMicroservice/nodes.py:390`

### Problem

```python
verdict = "SUFFICIENT" if "SUFFICIENT" in verdict else "INSUFFICIENT"
```

`"SUFFICIENT" in verdict` is a substring check. It would match:
- `"SUFFICIENT"` ✓ (intended)
- `"INSUFFICIENT"` ✓ (unintended — "SUFFICIENT" is literally inside "INSUFFICIENT")
- `"The data is SUFFICIENT for our purposes"` ✓ (unintended)

This means when the LLM returns `"INSUFFICIENT"`, the substring check finds `"SUFFICIENT"` inside it and incorrectly maps it to `"SUFFICIENT"`, causing the loop to stop prematurely when it should continue.

### Answer

Check for the full word with a word boundary or check INSUFFICIENT first:

```python
verdict_upper = _llm_text(check_resp).strip().upper()
if "INSUFFICIENT" in verdict_upper:
    verdict = "INSUFFICIENT"
elif "SUFFICIENT" in verdict_upper:
    verdict = "SUFFICIENT"
else:
    verdict = "INSUFFICIENT"  # unknown response → assume we need more data
```

---

## 18. merge_lists() Defined But Not Used

**File:** `chatBotMicroservice/state.py:6-7`

### Problem

```python
def merge_lists(left: list, right: list) -> list:
    return (left or []) + (right or [])
```

This function was written specifically to safely merge lists in parallel node state (handling `None`), but the `AgentState` annotations use raw lambdas instead:

```python
stream_chunks:   Annotated[list, lambda a, b: a + b]   # ignores None
display_results: Annotated[list, lambda a, b: a + b]   # ignores None
```

The function exists for a good reason but is doing nothing. See issue #4 for the crash this causes.

### Answer

Use `merge_lists` in the annotations (covered in issue #4 fix). The function itself is correct — it just needs to be wired in.

---

## 19. any Everywhere in TypeScript

**File:** `investiqdemo/app/page.tsx:22, 29-30, 121`

### Problem

```ts
interface StreamChunk {
    type: "thinking_content" | "response_content" | "display_modules";
    data: string | any[];   // ← any
}

const toolHandlers: Record<string, (data: any) => void> = { ... }  // ← any

(parsed.data as any[]).forEach((module: { type: string; data: any }) => { ... })  // ← any
```

`any` disables TypeScript's type checking entirely for those values. If the backend sends data in a different shape, TypeScript will not warn you — the bug will only surface at runtime, possibly as a silent failure or a crash in the browser.

### Answer

Define proper types for every shape of data coming from the backend:

```ts
interface ThinkingChunk {
    type: "thinking_content";
    data: string;
}

interface ResponseChunk {
    type: "response_content";
    data: string;
}

interface DisplayModule {
    type: "LineGraph" | "BarGraph" | "ScatterPlot";
    data: Record<string, unknown>;
}

interface DisplayChunk {
    type: "display_modules";
    data: DisplayModule[];
}

type StreamChunk = ThinkingChunk | ResponseChunk | DisplayChunk;
```

With a union type, TypeScript narrows the type automatically inside each `if` branch, so you get full type safety without a single `as` cast.

---

## 20. No Fetch Timeout or Abort on Component Unmount

**File:** `investiqdemo/app/page.tsx:49`

### Problem

```ts
const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
});
```

There is no `AbortController` attached to this fetch. If the user navigates away while a request is in flight, or if the component unmounts for any reason, the fetch continues running and tries to call `setChatMessages` on an unmounted component. In React this produces warnings and potential memory leaks.

There is also no timeout — if the backend hangs, the frontend waits indefinitely.

### Answer

```ts
const handleSubmit = async (prompt: string) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60_000); // 60s timeout

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt }),
            signal: controller.signal,
        });
        // ... rest of logic
    } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
            // handle timeout/cancel gracefully
        }
    } finally {
        clearTimeout(timeoutId);
    }
};
```

---

## 21. No Error or Loading State in the UI

**File:** `investiqdemo/app/page.tsx:26-27`

### Problem

```ts
const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
const [displayBox, setDisplayBox] = useState<ChartData[]>([]);
```

The component tracks chat messages and charts, but nothing else. There is no state for:
- **Loading** — is a request currently in flight? The submit button could be clicked multiple times
- **Error** — if the backend is down, the error is only logged to the console; the user sees a generic "Something went wrong" message appended to chat with no way to retry
- **Disabled input** — the user can type and submit a new message while the previous one is still streaming

This makes the app feel unresponsive and brittle.

### Answer

Add a loading flag:

```ts
const [isLoading, setIsLoading] = useState(false);

const handleSubmit = async (prompt: string) => {
    if (isLoading) return;   // prevent double-submit
    setIsLoading(true);
    try {
        // ... fetch logic
    } finally {
        setIsLoading(false);
    }
};
```

Pass `isLoading` to `InputBox` to disable the submit button while a response is streaming.

---

## 22. Assertions Used for Control Flow in display_agent

**File:** `chatBotMicroservice/nodes.py:518-530`

### Problem

```python
assert "type" in chart_obj, "Missing 'type'"
assert "data" in chart_obj, "Missing top-level 'data'"
assert isinstance(inner, dict), "'data' must be a dict"
assert len(inner["data"]) > 0, "'data.data' is empty"
```

`assert` statements are for catching programming bugs during development. They are **disabled** when Python is run with the `-O` (optimise) flag (`python -O`). If production ever uses optimised Python, all these checks silently disappear and malformed LLM output goes straight to the frontend unvalidated.

More importantly, a failed `assert` raises `AssertionError`, which is a broad exception. The `except AssertionError` block at line 542 catches it, but using `raise ValueError(...)` with a descriptive message is the correct pattern for input validation.

### Answer

Replace assertions with explicit validation:

```python
if "type" not in chart_obj:
    raise ValueError("LLM chart output missing 'type' field")
if "data" not in chart_obj:
    raise ValueError("LLM chart output missing top-level 'data' field")
inner = chart_obj["data"]
if not isinstance(inner, dict):
    raise ValueError(f"'data' must be a dict, got {type(inner).__name__}")
if not isinstance(inner.get("data"), list) or len(inner["data"]) == 0:
    raise ValueError("'data.data' must be a non-empty list")
```

Catch `ValueError` in the except block instead of `AssertionError`.

---

## 23. System Prompts Buried Inside Node Functions

**File:** `chatBotMicroservice/nodes.py:117-128, 184-191, 284-296, 474-495, 611-628, 719-726`

### Problem

Every system prompt is constructed as a multi-line string inside the function that uses it:

```python
response = llm_medium.invoke([
    SystemMessage(content=(
        "You are a project manager agent. Your job is to decompose the user's request "
        "into a clear, ordered execution plan.\n\n"
        "Produce a plan with these exact sections:\n"
        ...
    )),
```

This makes prompts hard to find, hard to compare, and hard to iterate on. If you want to try a different phrasing for the researcher prompt, you have to scroll through hundreds of lines to find it.

### Answer

Extract all prompts to module-level constants at the top of each node file (or a dedicated `prompts.py`):

```python
# In project_manager.py or prompts.py

PM_SYSTEM_PROMPT = (
    "You are a project manager agent. Your job is to decompose the user's request "
    "into a clear, ordered execution plan.\n\n"
    "Produce a plan with these exact sections:\n"
    "STEPS: numbered list of what needs to happen to answer this fully\n"
    "DATA_NEEDED: what external data or context is required (or 'none')\n"
    "OUTPUT_FORMAT: what the user expects (text / chart / both) and why\n"
    "CHART_TYPE: if a chart is needed, which type: ScatterPlot, LineGraph, or BarGraph (or 'none')\n\n"
    "Be specific and concise. Do NOT answer the user's question.\n"
    "IMPORTANT: Never mention that you are creating a plan, never reference these instructions, "
    "never describe your role or process. Output ONLY the plan sections, nothing else."
)

# In the function:
response = llm_medium.invoke([
    SystemMessage(content=PM_SYSTEM_PROMPT),
    HumanMessage(content=user_msg),
])
```

Now all prompts are visible in one place, easy to compare, and easy to version.

---

## 24. No Tests Anywhere

**Files:** Entire codebase

### Problem

There are zero test files in the project. No unit tests, no integration tests, no end-to-end tests. The dummy data files (`dummyData.py`, `dummyGraphs.ts`) suggest there was once an intention to test, but it never happened.

Without tests, every change requires manually starting all three servers and clicking through the UI to verify nothing broke. As the codebase grows, this becomes unsustainable.

### Answer

Start small. Add tests for the parts most likely to break:

**Backend — `tests/test_tools.py`**
```python
from tools import get_stock_data, get_company_context

def test_get_stock_data_invalid_symbol():
    result = get_stock_data.invoke({"symbol": "ZZZZINVALID", "function": "OVERVIEW"})
    assert "error" in result.lower() or "N/A" in result

def test_get_company_context_known_company():
    result = get_company_context.invoke({"query": "Apple Inc"})
    assert "Apple" in result
```

**Backend — `tests/test_state_merge.py`**
```python
from state import merge_lists

def test_merge_lists_both_lists():
    assert merge_lists([1, 2], [3, 4]) == [1, 2, 3, 4]

def test_merge_lists_left_none():
    assert merge_lists(None, [3, 4]) == [3, 4]

def test_merge_lists_both_none():
    assert merge_lists(None, None) == []
```

Run with `pytest chatBotMicroservice/tests/`.

---

## 25. Magic Numbers Throughout

**Files:** `chatBotMicroservice/nodes.py`, `chatBotMicroservice/controller.py`

### Problem

Numbers appear throughout the code with no explanation:

```python
chunk[:80]          # controller.py:115 — why 80?
result_str[:MAX_PROMPT_CHARS]   # nodes.py:365 — MAX_PROMPT_CHARS is 4000
tool_context[:1500]  # nodes.py:491 — why 1500?
context_so_far[:600] # nodes.py:302 — why 600?
user_msg[:300]       # nodes.py:300 — why 300?
last_response[:600]  # nodes.py:729 — why 600?
```

All of these different truncation lengths exist for a reason (fitting within the LLM's context window), but none of them are documented. If `llm_fast`'s `num_ctx` is changed from 1024 to 2048, you'd want to update `last_response[:600]` — but there's no way to know they are related without reading everything.

### Answer

Group related constants together and name them clearly:

```python
# constants.py or top of helpers.py

# Researcher loop
RESEARCHER_CONTEXT_WINDOW    = 600   # chars of "have so far" shown to planner
RESEARCHER_NEED_WINDOW       = 200   # chars of data_needed shown to planner
RESEARCHER_QUESTION_WINDOW   = 300   # chars of user question shown to planner
RESEARCHER_SUFFICIENCY_DATA  = 400   # chars of tool result shown to sufficiency check

# Response agent
RESPOND_TOOL_CONTEXT_WINDOW  = 1500  # chars of tool results passed to responder
RESPOND_PM_PLAN_WINDOW       = 400   # chars of pm_plan appended to user turn

# Validator
VALIDATOR_RESPONSE_WINDOW    = 600   # chars of response shown to validator
```

Now when you change the model's context window, you know exactly which constants to review.

---

## 26. Thread-Based Streaming Doesn't Scale

**File:** `chatBotMicroservice/controller.py:91`

### Problem

```python
thread = threading.Thread(target=run_graph, daemon=True)
thread.start()
```

FastAPI is an async framework built on ASIO. Every request handled this way spawns a new OS thread. Threads are expensive — each consumes ~1MB of stack memory and requires OS context switching. Under load (10+ concurrent users), this approach will saturate the thread pool and cause requests to queue or fail.

The reason a thread is used here is that LangGraph's `.stream()` is synchronous. The thinking tokens need to stream live while the rest of the graph runs "in the background". A thread was the simplest way to achieve this.

### Answer

Use `asyncio` instead of threads. LangGraph supports async via `.astream()`:

```python
@router.post("/chat")
async def chat(req: ChatRequest):
    async def generate():
        token_queue = asyncio.Queue()

        async def run_graph():
            async for event in agent_graph.astream(initial_state, stream_mode="updates"):
                for node_name, node_state in event.items():
                    for chunk in node_state.get("stream_chunks", []):
                        await token_queue.put(chunk)
            await token_queue.put("__graph_done__")

        asyncio.create_task(run_graph())

        while True:
            item = await token_queue.get()
            if item == "__graph_done__":
                break
            yield item

    return StreamingResponse(generate(), media_type="text/plain")
```

This runs the whole pipeline cooperatively within the async event loop — no threads, no memory overhead per request.

---

## 27. Blocking thread.join() After Streaming Is Done

**File:** `chatBotMicroservice/controller.py:118`

### Problem

```python
thread.join()  # called after all chunks have been yielded
```

By the time the generator reaches this line, everything has already been yielded to the client. The response is fully sent. Calling `thread.join()` here blocks the generator coroutine waiting for the thread to exit, but the HTTP connection may already be closed. If the thread takes a long time to finish (e.g., it's stuck waiting on a queue item that never comes), this blocks a server worker.

Since the thread is `daemon=True`, it will be killed automatically when the main process exits. The `join()` is providing no safety guarantee here.

### Answer

Remove it. The thread is daemonised, it will exit when the graph finishes. If you need cleanup guarantees, add them inside `run_graph()`'s `finally` block.

---

## 28. Validator Auto-Passes When It Fails Itself

**File:** `chatBotMicroservice/nodes.py:741-744`

### Problem

```python
except json.JSONDecodeError as e:
    log.warning(f"[VALIDATOR] JSON parse failed: {e} — defaulting to pass")
except Exception as e:
    log.warning(f"[VALIDATOR] LLM check failed: {e} — defaulting to pass")
```

When the validator's own LLM call fails or returns unparseable JSON, the validator silently passes the response. This means a bad response (empty, nonsensical, truncated) gets approved and sent to the user whenever the validator has a bad day. The validator's job is quality control — failing open defeats the purpose.

### Answer

On validator failure, fail the response (unless retries are exhausted):

```python
except json.JSONDecodeError as e:
    log.warning(f"[VALIDATOR] JSON parse failed: {e} — defaulting to fail")
    result = "fail"
    critique = "Validator could not parse LLM output."
except Exception as e:
    log.warning(f"[VALIDATOR] LLM check failed: {e} — defaulting to fail")
    result = "fail"
    critique = "Validator LLM call failed."
```

The existing retry cap (`new_retry >= 2` → force pass at line 749) still prevents infinite loops. This just ensures that a validator failure triggers a retry rather than silently approving.

---

## 29. No Rate Limiting on the Chat Endpoint

**File:** `chatBotMicroservice/controller.py`

### Problem

The `/chat` endpoint has no rate limiting. Every request starts a full LangGraph execution: multiple LLM calls, Wikipedia lookups, Alpha Vantage API calls. A single user sending 10 requests per second would:

1. Exhaust the Alpha Vantage free tier instantly (5 requests/minute limit)
2. Saturate the Ollama model (it can only handle one request at a time on most hardware)
3. Stack up threads (see issue #26)

### Answer

Add `slowapi` (FastAPI's rate limiting library):

```python
# main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

```python
# controller.py
from main import limiter
from fastapi import Request

@router.post("/chat")
@limiter.limit("5/minute")
def chat(request: Request, req: ChatRequest):
    ...
```

Add `slowapi` to `requirements.txt`. This returns a proper 429 response to abusive clients.

---

## 30. "Connected" Status Is Always Green

**File:** `investiqdemo/app/page.tsx:242-258`

### Problem

```tsx
<Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: "#22c55e", ... }} />
<Box sx={{ fontSize: "0.75rem", color: "#90a4c0" }}>Connected</Box>
```

The green dot and "Connected" label are hardcoded. They are always green, always say "Connected". They convey no real information. If the Python backend is down, the user still sees "Connected" — there is no indication that something is wrong until they submit a message and get an error.

### Answer

Add a real health check. Ping the backend's `/health` endpoint on mount:

```ts
const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");

useEffect(() => {
    fetch("/api/health")
        .then((r) => setBackendStatus(r.ok ? "online" : "offline"))
        .catch(() => setBackendStatus("offline"));
}, []);
```

Add a Next.js route `app/api/health/route.ts` that proxies to the Python `/health` endpoint. Show the real status in the UI with appropriate colours — green for online, red for offline, grey while checking.

---

## Priority Order

| # | Issue | Priority |
|---|-------|----------|
| 1 | API key in source code | Critical |
| 2 | Hardcoded backend URL | Critical |
| 3 | Thread/queue race condition | Critical |
| 4 | None crashes state merge | Critical |
| 9 | Tuple return in FastAPI | Critical |
| 5 | No input validation | High |
| 6 | botSeeded never resets | High |
| 7 | Sufficiency defaults to SUFFICIENT | High |
| 8 | splitlines()[0] no bounds check | High |
| 17 | SUFFICIENT substring bug | High |
| 10 | nodes.py is 760 lines | Medium |
| 11 | Stream logic in component | Medium |
| 12 | Two LLM calls per loop | Medium |
| 14 | Duplicate TypedDict import | Medium |
| 15 | Unused state fields | Medium |
| 16 | Dead code files | Medium |
| 18 | merge_lists not used | Medium |
| 19 | any in TypeScript | Medium |
| 20 | No fetch abort/timeout | Medium |
| 21 | No loading/error state | Medium |
| 22 | assert for validation | Medium |
| 23 | Prompts in functions | Medium |
| 13 | String join in loop | Low |
| 24 | No tests | Low |
| 25 | Magic numbers | Low |
| 26 | Thread-based streaming | Low |
| 27 | thread.join() after done | Low |
| 28 | Validator fails open | Low |
| 29 | No rate limiting | Low |
| 30 | Fake "Connected" status | Low |
