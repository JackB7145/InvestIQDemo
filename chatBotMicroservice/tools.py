import requests
import json
from langchain_core.tools import tool
from dummyData import tools_response

USER_DISPLAY_TOOLS = {"get_graph_data"}
CONTEXT_TOOLS = {"get_company_context"}


@tool
def get_graph_data(graph_type: str = "all") -> list:
    """Returns graph/chart data for visualization.
    Call this when the user asks for graphs, charts, visualizations, or data plots.
    Output NOTHING else — the frontend renders the data automatically.

    Args:
        graph_type: 'LineGraph', 'BarGraph', 'ScatterPlot', or 'all'.
    """
    if graph_type == "all":
        return tools_response
    return [g for g in tools_response if g["type"] == graph_type]


@tool
def get_company_context(query: str) -> str:
    """Retrieves context from Wikipedia to help answer the user's question.
    Call this when the user asks about a company, person, or topic needing background info.

    Args:
        query: The topic to look up (e.g. 'Apple Inc', 'Elon Musk').
    """
    try:
        search_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query,
                    "srlimit": 1, "format": "json"},
            timeout=10,
            headers={"User-Agent": "CompanyContextBot/1.0"},
        )
        results = search_resp.json().get("query", {}).get("search", [])
        if not results:
            return f"No Wikipedia article found for '{query}'."

        title = results[0]["title"]
        extract_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "prop": "extracts", "exintro": True,
                    "explaintext": True, "titles": title, "format": "json", "redirects": "1"},
            timeout=10,
            headers={"User-Agent": "CompanyContextBot/1.0"},
        )
        pages = extract_resp.json().get("query", {}).get("pages", {})
        if not pages or "-1" in pages:
            return f"Wikipedia article '{title}' not found or empty."

        extract = next(iter(pages.values())).get("extract", "").strip()
        if not extract:
            return f"No content found for '{title}'."

        trimmed = extract[:2000] + ("..." if len(extract) > 2000 else "")
        return f"[Wikipedia: {title}]\n\n{trimmed}"

    except Exception as e:
        return f"Error retrieving context: {str(e)}"


TOOLS = [get_graph_data, get_company_context]
TOOL_MAP = {t.name: t for t in TOOLS}