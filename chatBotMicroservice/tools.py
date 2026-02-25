import os
import requests
import json
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()
ALPHAVANTAGE_API_KEY = os.environ["ALPHAVANTAGE_API_KEY"]
ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"

USER_DISPLAY_TOOLS = {"get_graph_data"}
CONTEXT_TOOLS = {"get_company_context", "get_stock_data"}

# =============================================================================
# GRAPH SCHEMAS
#
# These are passed to the LLM so it knows exactly what structure to produce.
# The LLM fills in real data based on the user's question — no dummy data.
# =============================================================================

# =============================================================================
# GRAPH SCHEMAS
#
# These define the exact JSON structure the LLM must produce for each chart
# type. The structure matches what the frontend renderer expects:
#   { "type": "...", "data": { "title": "...", "data": [...], "series": [...] } }
#
# The LLM receives these as templates and must fill in real data values
# relevant to the user's question — replacing placeholder strings/numbers.
# =============================================================================

GRAPH_SCHEMAS = {
    "LineGraph": {
        "type": "LineGraph",
        "data": [
            {
                "x": ["<int or float>"],       # array of numbers, timestamps or sequential
                "y": ["<float>"],             # array of numeric values
                "name": "<str series name>",  # str
                "type": "scatter",
                "mode": "lines+markers",
                "line": {"color": "<str color>"},
            }
        ],
        "layout": {
            "title": "<str title>",
            "xaxis": {"title": "<str x-axis label>"},
            "yaxis": {"title": "<str y-axis label>"},
        },
        "dynamic_traces": True,
    },
    "BarGraph": {
        "type": "BarGraph",
        "data": [
            {
                "x": ["<str category>"],     # array of category labels
                "y": ["<float>"],            # array of numeric values
                "name": "<str metric name>",
                "type": "bar",
                "marker": {"color": "<str color>"},
            }
        ],
        "layout": {
            "title": "<str title>",
            "xaxis": {"title": "<str x-axis label>"},
            "yaxis": {"title": "<str y-axis label>"},
        },
        "dynamic_traces": True,
    },
    "ScatterPlot": {
        "type": "ScatterPlot",
        "data": [
            {
                "x": ["<float>"],           # array of x-values
                "y": ["<float>"],           # array of y-values
                "name": "<str trace name>",
                "mode": "markers",
                "marker": {"color": "<str color>"},
            }
        ],
        "layout": {
            "title": "<str title>",
            "xaxis": {"title": "<str x-axis label>"},
            "yaxis": {"title": "<str y-axis label>"},
        },
        "dynamic_traces": True,
    },
}

@tool
def get_graph_data(graph_type: str = "all") -> list:
    """Returns a JSON template the LLM must fill with real data for chart rendering.
    Call this when the user asks for graphs, charts, visualizations, or data plots.

    The returned template has this exact structure the frontend expects:
      { "type": "...", "data": { "title": "...", "data": [...], "series": [...] } }

    The LLM must take this template and replace all placeholder values
    (<descriptive title>, <metric>, 0, etc.) with real data values relevant
    to the user's question. The filled object must be emitted as display_modules.

    Args:
        graph_type: 'LineGraph', 'BarGraph', 'ScatterPlot', or 'all'.
    """
    if graph_type == "all":
        return list(GRAPH_SCHEMAS.values())
    schema = GRAPH_SCHEMAS.get(graph_type)
    return [schema] if schema else list(GRAPH_SCHEMAS.values())


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


@tool
def get_stock_data(symbol: str, function: str = "OVERVIEW", limit: int | None = None) -> str:
    """
    Retrieves real financial data from Alpha Vantage for a given stock ticker.
    Args:
        symbol: The stock ticker symbol (e.g. 'AAPL', 'TSLA', 'MSFT').
        function: The type of data to retrieve.
        limit: Optional. Limits the number of items returned (e.g., days, reports, earnings). Defaults depend on function.
    """
    try:
        params = {
            "function": function,
            "symbol": symbol.upper().strip(),
            "apikey": ALPHAVANTAGE_API_KEY,
        }

        # Default output size
        if function == "TIME_SERIES_DAILY":
            params["outputsize"] = "compact"

        resp = requests.get(ALPHAVANTAGE_BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Alpha Vantage errors / rate limits
        if "Error Message" in data:
            return f"Alpha Vantage error for '{symbol}': {data['Error Message']}"
        if "Note" in data:
            return f"Alpha Vantage rate limit reached. Try again in a minute. ({data['Note']})"
        if "Information" in data:
            return f"Alpha Vantage API notice: {data['Information']}"

        # OVerview
        if function == "OVERVIEW":
            keys = [
                "Name", "Symbol", "Exchange", "Sector", "Industry",
                "MarketCapitalization", "PERatio", "EPS", "DividendYield",
                "52WeekHigh", "52WeekLow", "AnalystTargetPrice",
                "RevenuePerShareTTM", "ProfitMargin", "OperatingMarginTTM",
                "ReturnOnEquityTTM", "RevenueTTM", "GrossProfitTTM", "Description",
            ]
            summary = {k: data.get(k, "N/A") for k in keys}
            lines = [f"[Alpha Vantage: {symbol.upper()} Overview]"]
            for k, v in summary.items():
                if k == "Description":
                    lines.append(f"\nDescription: {v[:400]}{'...' if len(str(v)) > 400 else ''}")
                else:
                    lines.append(f"{k}: {v}")
            return "\n".join(lines)

        # GLOBAL_QUOTE
        elif function == "GLOBAL_QUOTE":
            q = data.get("Global Quote", {})
            if not q:
                return f"No quote data found for '{symbol}'."
            return (
                f"[Alpha Vantage: {symbol.upper()} Quote]\n"
                f"Price: {q.get('05. price', 'N/A')}\n"
                f"Change: {q.get('09. change', 'N/A')} ({q.get('10. change percent', 'N/A')})\n"
                f"Open: {q.get('02. open', 'N/A')}\n"
                f"High: {q.get('03. high', 'N/A')}\n"
                f"Low: {q.get('04. low', 'N/A')}\n"
                f"Volume: {q.get('06. volume', 'N/A')}\n"
                f"Previous Close: {q.get('08. previous close', 'N/A')}\n"
                f"Latest Trading Day: {q.get('07. latest trading day', 'N/A')}"
            )

        # TIME_SERIES_DAILY
        elif function == "TIME_SERIES_DAILY":
            series = data.get("Time Series (Daily)", {})
            if not series:
                return f"No daily price data found for '{symbol}'."
            days = sorted(series.keys(), reverse=True)[:limit or 30]
            lines = [f"[Alpha Vantage: {symbol.upper()} Daily Prices (last {len(days)} days)]"]
            for day in days:
                d = series[day]
                lines.append(
                    f"{day}: open={d.get('1. open')} high={d.get('2. high')} "
                    f"low={d.get('3. low')} close={d.get('4. close')} vol={d.get('5. volume')}"
                )
            return "\n".join(lines)

        # INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW
        report_functions = ["INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW"]
        if function in report_functions:
            report_key_map = {
                "INCOME_STATEMENT": "annualReports",
                "BALANCE_SHEET": "annualReports",
                "CASH_FLOW": "annualReports",
            }
            reports = data.get(report_key_map[function], [])
            if not reports:
                return f"No {function.replace('_',' ').lower()} data found for '{symbol}'."
            lines = [f"[Alpha Vantage: {symbol.upper()} {function.replace('_',' ')} (Annual)]"]
            for r in reports[:limit or 3]:
                fiscal = r.get("fiscalDateEnding", "N/A")
                if function == "INCOME_STATEMENT":
                    lines.append(
                        f"\nFiscalYear: {fiscal}\n"
                        f"  Revenue: {r.get('totalRevenue', 'N/A')}\n"
                        f"  Gross Profit: {r.get('grossProfit', 'N/A')}\n"
                        f"  Net Income: {r.get('netIncome', 'N/A')}\n"
                        f"  Operating Income: {r.get('operatingIncome', 'N/A')}\n"
                        f"  EBITDA: {r.get('ebitda', 'N/A')}"
                    )
                elif function == "BALANCE_SHEET":
                    lines.append(
                        f"\nFiscalYear: {fiscal}\n"
                        f"  Total Assets: {r.get('totalAssets', 'N/A')}\n"
                        f"  Total Liabilities: {r.get('totalLiabilities', 'N/A')}\n"
                        f"  Shareholder Equity: {r.get('totalShareholderEquity', 'N/A')}\n"
                        f"  Cash & Equivalents: {r.get('cashAndCashEquivalentsAtCarryingValue', 'N/A')}\n"
                        f"  Long Term Debt: {r.get('longTermDebt', 'N/A')}"
                    )
                elif function == "CASH_FLOW":
                    lines.append(
                        f"\nFiscalYear: {fiscal}\n"
                        f"  Operating Cash Flow: {r.get('operatingCashflow', 'N/A')}\n"
                        f"  Capital Expenditures: {r.get('capitalExpenditures', 'N/A')}\n"
                        f"  Free Cash Flow: {r.get('freeCashFlow', 'N/A')}\n"
                        f"  Dividend Payout: {r.get('dividendPayout', 'N/A')}"
                    )
            return "\n".join(lines)

        # EARNINGS
        elif function == "EARNINGS":
            annual_reports = data.get("annualEarnings", [])
            quarterly_reports = data.get("quarterlyEarnings", [])
            lines = [f"[Alpha Vantage: {symbol.upper()} Annual EPS]"]
            for r in annual_reports[:limit or 5]:
                lines.append(f"  {r.get('fiscalDateEnding', 'N/A')}: EPS={r.get('reportedEPS', 'N/A')}")
            if quarterly_reports:
                lines.append("\nQuarterly Earnings:")
                for r in quarterly_reports[:limit or 8]:
                    lines.append(
                        f"  {r.get('fiscalDateEnding', 'N/A')}: "
                        f"reported={r.get('reportedEPS', 'N/A')} "
                        f"estimated={r.get('estimatedEPS', 'N/A')} "
                        f"surprise={r.get('surprisePercentage', 'N/A')}%"
                    )
            return "\n".join(lines)

        # fallback: raw JSON (truncated)
        raw = json.dumps(data, indent=2)
        return f"[Alpha Vantage: {symbol.upper()} / {function}]\n{raw[:2000]}"

    except requests.exceptions.Timeout:
        return f"Request to Alpha Vantage timed out for '{symbol}'."
    except requests.exceptions.RequestException as e:
        return f"Network error fetching data for '{symbol}': {str(e)}"
    except Exception as e:
        return f"Unexpected error fetching stock data for '{symbol}': {str(e)}"

TOOLS = [get_graph_data, get_company_context, get_stock_data]

TOOL_MAP = {t.name: t for t in TOOLS}

TOOL_LIST = {t.name: t.description for t in TOOLS}