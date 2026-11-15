"""Tests for the mock planner. Every expectation is computed from
data/sales.csv by hand — if the CSV changes, these numbers change too.
"""

import os

import pytest

from ask_csv import answer, load_csv

HERE = os.path.dirname(__file__)
HEADERS, ROWS = load_csv(os.path.join(HERE, "data", "sales.csv"))


def test_load_csv_has_18_rows_and_expected_headers():
    assert HEADERS == ["month", "region", "product", "units", "revenue"]
    assert len(ROWS) == 18


def test_total_revenue():
    result = answer("What is the total revenue?", HEADERS, ROWS)
    assert "18,250.00" in result["text"]
    assert result["rows_used"] == 18
    assert result["mode"] == "mock"


def test_total_revenue_with_filter():
    result = answer("What is the total revenue in the North?", HEADERS, ROWS)
    assert "7,300.00" in result["text"]
    assert result["rows_used"] == 6


def test_total_revenue_for_a_product():
    result = answer("What is the total revenue for Widget?", HEADERS, ROWS)
    assert "9,400.00" in result["text"]
    assert result["rows_used"] == 9


def test_average_revenue():
    result = answer("What is the average revenue?", HEADERS, ROWS)
    assert "1,013.89" in result["text"]


def test_highest_revenue_row():
    result = answer("What is the highest revenue?", HEADERS, ROWS)
    assert "1,500.00" in result["text"]
    assert "Apr" in result["text"] and "North" in result["text"]


def test_lowest_revenue_row():
    result = answer("What is the lowest revenue?", HEADERS, ROWS)
    assert "600.00" in result["text"]
    assert "Gizmo" in result["text"]


def test_count_with_filter():
    result = answer("How many Widget rows are there?", HEADERS, ROWS)
    assert result["text"].startswith("9 rows match")


def test_top_products_by_revenue():
    result = answer("Top 2 products by revenue", HEADERS, ROWS)
    assert "1. Widget: $9,400.00" in result["text"]
    assert "2. Gadget: $5,250.00" in result["text"]


def test_filter_only_lists_matching_rows():
    result = answer("Show me the South rows", HEADERS, ROWS)
    assert result["rows_used"] == 6
    assert "region=South" in result["text"]


def test_unknown_question_is_honest_not_a_guess():
    result = answer("Will revenue grow next quarter?", HEADERS, ROWS)
    assert "couldn't parse" in result["text"]
    assert result["rows_used"] == 0


def test_sales_is_understood_as_revenue():
    result = answer("What are the total sales?", HEADERS, ROWS)
    assert "18,250.00" in result["text"]


def test_empty_csv_has_nothing_to_answer():
    result = answer("What is the total revenue?", ["month", "revenue"], [])
    assert "No rows" in result["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
