"""
Root-level conftest.py — loaded by pytest for every test in the project.

Registers shared fixture plugins so fixtures defined in tests/fixtures/
are available to ALL test files regardless of their location (apps/, tests/, etc.)
"""

# Load shared fixture plugins globally
pytest_plugins = [
    "tests.fixtures.auth",
    "tests.fixtures.db",
]
