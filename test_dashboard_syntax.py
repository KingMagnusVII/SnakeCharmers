"""Regression check: the Streamlit dashboard must remain valid Python syntax."""

import ast
from pathlib import Path


def test_dashboard_is_valid_python_syntax():
    dashboard_path = Path(__file__).parent / "dashboard.py"
    source = dashboard_path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(dashboard_path))
