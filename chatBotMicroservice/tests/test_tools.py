"""
Tests for tools.py — exercises tool logic without hitting real APIs where possible.
Run with: pytest chatBotMicroservice/tests/test_tools.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import get_graph_data, GRAPH_SCHEMAS


# =============================================================================
# get_graph_data — schema retrieval (no network call)
# =============================================================================

def test_get_graph_data_line():
    result = get_graph_data.invoke({"graph_type": "LineGraph"})
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["type"] == "LineGraph"


def test_get_graph_data_bar():
    result = get_graph_data.invoke({"graph_type": "BarGraph"})
    assert isinstance(result, list)
    assert result[0]["type"] == "BarGraph"


def test_get_graph_data_scatter():
    result = get_graph_data.invoke({"graph_type": "ScatterPlot"})
    assert isinstance(result, list)
    assert result[0]["type"] == "ScatterPlot"


def test_get_graph_data_all():
    result = get_graph_data.invoke({"graph_type": "all"})
    assert len(result) == len(GRAPH_SCHEMAS)


def test_get_graph_data_unknown_returns_all():
    # Unknown graph type should fall back to all schemas
    result = get_graph_data.invoke({"graph_type": "PieChart"})
    assert len(result) == len(GRAPH_SCHEMAS)


def test_graph_schemas_have_required_keys():
    for name, schema in GRAPH_SCHEMAS.items():
        assert "type" in schema, f"{name} schema missing 'type'"
        assert "data" in schema, f"{name} schema missing 'data'"
        inner = schema["data"]
        assert "title" in inner, f"{name} schema missing 'data.title'"
        assert "data" in inner,  f"{name} schema missing 'data.data'"
        assert "series" in inner, f"{name} schema missing 'data.series'"


# =============================================================================
# Researcher helpers — _is_tool_result_an_error
# =============================================================================

from nodes.researcher import _is_tool_result_an_error


def test_error_detection_alpha_vantage_note():
    assert _is_tool_result_an_error("Note: Thank you for using Alpha Vantage") is True


def test_error_detection_rate_limit():
    assert _is_tool_result_an_error("rate limit exceeded") is True


def test_error_detection_clean_result():
    assert _is_tool_result_an_error("AAPL: Price=195.42, Volume=1234567") is False


def test_error_detection_no_article():
    assert _is_tool_result_an_error("No Wikipedia article found for 'XYZNOTREAL'.") is True
