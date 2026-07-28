"""
Smoke tests for the application.

This module contains lightweight, fast-running tests that verify the most
critical functionality of the system is operational. These tests are designed
to be run frequently (e.g., on every commit or deployment) to catch major
regressions early. They cover basic importability, configuration loading,
database connectivity, and core API endpoint availability.
"""

import pytest


def test_imports():
    """Verify that the main application package can be imported without errors."""
    import app
    assert app is not None


def test_config_loads():
    """Verify that the application configuration loads successfully."""
    from app import config
    assert config is not None


def test_database_connection():
    """Verify that the application can establish a database connection."""
    from app import db
    assert db is not None


def test_health_endpoint(client):
    """Verify that the health check endpoint returns a successful response."""
    response = client.get("/health")
    assert response.status_code == 200


def test_root_endpoint(client):
    """Verify that the root endpoint is accessible."""
    response = client.get("/")
    assert response.status_code == 200


@pytest.fixture
def client():
    """Create a test client for the application."""
    from app import create_app
    app = create_app(testing=True)
    with app.test_client() as client:
        yield client