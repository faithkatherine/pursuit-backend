"""
Root-level conftest.py — loaded by pytest for every test in the project.

Registers shared fixture plugins so fixtures defined in tests/fixtures/
are available to ALL test files regardless of their location (apps/, tests/, etc.)
"""

# Load shared fixture plugins globally
pytest_plugins = [
    "apps.tests.fixtures.auth",
    "apps.tests.fixtures.db",
]
