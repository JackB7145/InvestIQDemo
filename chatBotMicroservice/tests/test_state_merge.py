"""
Tests for state.py — verifies that the merge_lists reducer correctly handles
None values that can occur when parallel nodes skip execution.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state import merge_lists


def test_merge_both_lists():
    assert merge_lists([1, 2], [3, 4]) == [1, 2, 3, 4]


def test_merge_left_none():
    assert merge_lists(None, [3, 4]) == [3, 4]


def test_merge_right_none():
    assert merge_lists([1, 2], None) == [1, 2]


def test_merge_both_none():
    assert merge_lists(None, None) == []


def test_merge_empty_lists():
    assert merge_lists([], []) == []


def test_merge_left_empty():
    assert merge_lists([], [1]) == [1]


def test_merge_preserves_order():
    result = merge_lists(["a", "b"], ["c", "d"])
    assert result == ["a", "b", "c", "d"]
