from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import ollama
import json
import requests
from dummyData import tools_response

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# TOOL DEFINITIONS
# UserDisplay tools → rendered on the frontend, no text summary
# Context tools     → fed back into the model as RAG context for a response
# =============================================================================

USER_DISPLAY_TOOLS = {"get_graph_data"}
CONTEXT_TOOLS = {"get_company_context"}

TOOLS = [
    # --- UserDisplay ---
    {
        "type": "function",
        "function": {
            "name": "get_graph_data",
            "description": (
                "Returns graph/chart data for visualization. "
                "Call this when the user asks for graphs, charts, visualizations, or data plots. "
                "When you call this tool, output NOTHING else — no explanation, no summary, no description. "
                "The frontend renders the data automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "graph_type": {
                        "type": "string",
                        "enum": ["LineGraph", "BarGraph", "ScatterPlot", "all"],
                        "description": "The type of graph to return. Infer from the user's request, or use 'all' if unspecified.",
                    }
                },
                "required": [],
            },
        },
    },
    # --- Context ---
    {
        "type": "function",
        "function": {
            "name": "get_company_context",
            "description": (
                "Retrieves relevant context from Wikipedia to help answer the user's question. "
                "Call this when the user asks about a company, person, concept, or topic "
                "that would benefit from factual background information. "
                "Use the returned context to inform and ground your response."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The topic or entity to look up on Wikipedia (e.g. 'Apple Inc', 'Elon Musk').",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

MODEL_OPTIONS = {"num_ctx": 8192, "thinking_budget": 1024}

# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def get_graph_data(graph_type: str = "all") -> list:
    if graph_type == "all":
        return tools_response
    return [g for g in tools_response if g["type"] == graph_type]

import requests

def get_company_context(query: str) -> str:
    try:
        # Step 1: Search for the best matching Wikipedia page
        search_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 1,
                "format": "json",
            },
            timeout=10,  # Increased timeout
            headers={"User-Agent": "CompanyContextBot/1.0"}  # Wikipedia prefers this
        )
        search_data = search_resp.json()
        results = search_data.get("query", {}).get("search", [])

        if not results:
            return f"No Wikipedia article found for '{query}'."

        title = results[0]["title"]

        # Step 2: Fetch the intro summary of that page (first ~500 words)
        extract_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": True,        # intro section only
                "explaintext": True,    # plain text, no HTML
                "titles": title,
                "format": "json",
                "redirects": "1",       # follow redirects
            },
            timeout=10,
            headers={"User-Agent": "CompanyContextBot/1.0"}
        )
        extract_data = extract_resp.json()
        pages = extract_data.get("query", {}).get("pages", {})
        
        # Handle missing page IDs better
        if not pages or "-1" in pages:
            return f"Wikipedia article '{title}' not found or empty."
            
        page = next(iter(pages.values()))
        extract = page.get("extract", "").strip()

        if not extract:
            return f"Wikipedia article for '{title}' had no extractable content."

        # Trim to ~2000 chars to stay within context budget
        trimmed = extract[:2000]
        if len(extract) > 2000:
            trimmed += "..."

        return f"[Wikipedia: {title}]\n\n{trimmed}"

    except requests.RequestException as e:
        return f"Failed to retrieve Wikipedia content: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


TOOL_MAP = {
    "get_graph_data": get_graph_data,
    "get_company_context": get_company_context,
}

MODEL = "qwen3:8b"

SYSTEM_PROMPT = (
    "You are a helpful chatbot assistant designed to answer user questions clearly and accurately. "
    "You have access to tools and should use them when appropriate. "
    "When reasoning, do NOT narrate tool usage in your thinking. Do not write things like "
    "'I will call get_graph_data' or 'I should use the tool'. Just call it silently. "
    "For any tool that returns display data (graphs, charts), output NOTHING in your response — "
    "no summary, no description, no acknowledgement. The frontend handles rendering automatically. "
    "For context tools, use the retrieved information to inform and ground your response."
)

class ChatRequest(BaseModel):
    prompt: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat")
def chat(req: ChatRequest):
    if not req.prompt.strip():
        return {"error": "Prompt is required"}, 400

    def generate():
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.prompt},
        ]

        # --- Phase 1: Stream first response (thinking + tool decision) ---
        gathered_thinking = ""
        gathered_content = ""
        gathered_tool_calls = []

        stream = ollama.chat(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            think=True,
            stream=True,
            options=MODEL_OPTIONS,
        )

        for chunk in stream:
            msg = chunk.message
            if msg.thinking:
                gathered_thinking += msg.thinking
                yield f"thought:{msg.thinking}\n"
            if msg.content:
                gathered_content += msg.content
            if msg.tool_calls:
                gathered_tool_calls.extend(msg.tool_calls)

        # No tool call — stream content and finish
        if not gathered_tool_calls:
            yield f"text:{gathered_content}\n"
            return

        # --- Phase 2: Execute tools, split by type ---
        messages.append({
            "role": "assistant",
            "content": gathered_content,
            "thinking": gathered_thinking,
            "tool_calls": [
                {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in gathered_tool_calls
            ],
        })

        display_results = []
        has_context_tools = False

        for tc in gathered_tool_calls:
            fn = TOOL_MAP.get(tc.function.name)
            if not fn:
                continue

            args = tc.function.arguments or {}
            result = fn(**args)

            if tc.function.name in USER_DISPLAY_TOOLS:
                display_results.append(result)
                messages.append({
                    "role": "tool",
                    "content": "Display data sent to frontend.",
                })

            elif tc.function.name in CONTEXT_TOOLS:
                has_context_tools = True
                messages.append({
                    "role": "tool",
                    "content": result if isinstance(result, str) else json.dumps(result),
                })

        # --- Phase 3: Stream follow-up grounded in context tools ---
        if has_context_tools:
            stream = ollama.chat(
                model=MODEL,
                messages=messages,
                think=True,
                stream=True,
                options=MODEL_OPTIONS,
            )

            followup_content = ""
            for chunk in stream:
                if chunk.message.thinking:
                    yield f"thought:{chunk.message.thinking}\n"
                if chunk.message.content:
                    followup_content += chunk.message.content

            if followup_content.strip():
                yield f"text:{followup_content}\n"

        # Flush display tool data to frontend
        if display_results:
            flat = []
            for r in display_results:
                flat.extend(r) if isinstance(r, list) else flat.append(r)
            yield f"tools:{json.dumps(flat)}\n"

    return StreamingResponse(generate(), media_type="text/plain")