"""
TDD Workflow Skill
Guides test-driven development for AUREM
"""

from typing import Dict, Any, List
import logging
from pathlib import Path

from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class TDDWorkflowSkill(BaseSkill):
    """
    Test-Driven Development workflow for AUREM
    
    Guides developers through:
    1. Write test first
    2. Run test (should fail)
    3. Write minimal code
    4. Run test (should pass)
    5. Refactor
    """
    
    def __init__(self):
        super().__init__(
            name="tdd-workflow",
            description="Test-driven development workflow for AUREM (pytest + Playwright)",
            category="development"
        )
        self.backend_test_dir = Path("/app/backend/tests")
        self.frontend_test_dir = Path("/app/frontend/src/__tests__")
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute TDD workflow
        
        Context:
        {
            "feature": "Add Slack connector",
            "type": "backend" | "frontend" | "e2e",
            "test_file": "test_slack_connector.py",  # optional
            "step": "write_test" | "run_test" | "write_code" | "refactor"
        }
        
        Returns:
        {
            "success": True,
            "current_step": "write_test",
            "next_step": "run_test",
            "checklist": [...],
            "test_template": "...",
            "guidance": "..."
        }
        """
        feature = context.get("feature", "")
        test_type = context.get("type", "backend")
        step = context.get("step", "write_test")
        
        if not feature:
            return {
                "success": False,
                "message": "Feature description required"
            }
        
        # Get workflow step
        if step == "write_test":
            return self._guide_write_test(feature, test_type, context)
        elif step == "run_test":
            return self._guide_run_test(feature, test_type, context)
        elif step == "write_code":
            return self._guide_write_code(feature, test_type, context)
        elif step == "refactor":
            return self._guide_refactor(feature, test_type, context)
        else:
            return {
                "success": False,
                "message": f"Unknown step: {step}"
            }
    
    def _guide_write_test(self, feature: str, test_type: str, context: Dict) -> Dict:
        """Guide: Write test first"""
        test_file = context.get("test_file")
        
        if test_type == "backend":
            test_dir = self.backend_test_dir
            test_template = self._get_backend_test_template(feature)
            framework = "pytest"
        elif test_type == "frontend":
            test_dir = self.frontend_test_dir
            test_template = self._get_frontend_test_template(feature)
            framework = "Jest + React Testing Library"
        else:  # e2e
            test_dir = self.backend_test_dir
            test_template = self._get_e2e_test_template(feature)
            framework = "Playwright"
        
        return {
            "success": True,
            "current_step": "write_test",
            "next_step": "run_test",
            "test_type": test_type,
            "test_directory": str(test_dir),
            "framework": framework,
            "test_template": test_template,
            "checklist": [
                "✅ Write test that describes desired behavior",
                "✅ Test should be specific and focused",
                "✅ Use descriptive test names",
                "✅ Include edge cases",
                "⏳ Run test (next step)"
            ],
            "guidance": f"Write a test for: {feature}. The test should FAIL initially (Red phase)."
        }
    
    def _guide_run_test(self, feature: str, test_type: str, context: Dict) -> Dict:
        """Guide: Run test (should fail)"""
        test_file = context.get("test_file", "test_feature.py")
        
        if test_type == "backend":
            command = f"pytest {test_file} -v"
        elif test_type == "frontend":
            command = f"yarn test {test_file}"
        else:
            command = f"pytest {test_file} --headed"
        
        return {
            "success": True,
            "current_step": "run_test",
            "next_step": "write_code",
            "command": command,
            "expected_result": "FAILED (this is correct! Red phase)",
            "checklist": [
                "✅ Test written",
                "✅ Run test with command above",
                "✅ Verify test FAILS (Red)",
                "⏳ Write minimal code to pass (next step)"
            ],
            "guidance": "The test should FAIL now. This proves the test is working correctly."
        }
    
    def _guide_write_code(self, feature: str, test_type: str, context: Dict) -> Dict:
        """Guide: Write minimal code to pass test"""
        return {
            "success": True,
            "current_step": "write_code",
            "next_step": "run_test_again",
            "checklist": [
                "✅ Test is failing (Red)",
                "✅ Write MINIMAL code to make test pass",
                "✅ Don't over-engineer",
                "✅ Just make it work",
                "⏳ Run test again (should pass - Green phase)"
            ],
            "guidance": f"Write the simplest code to make {feature} test pass. Don't add extra features.",
            "principles": [
                "YAGNI (You Aren't Gonna Need It)",
                "Keep it simple",
                "Make the test pass, nothing more"
            ]
        }
    
    def _guide_refactor(self, feature: str, test_type: str, context: Dict) -> Dict:
        """Guide: Refactor while keeping tests green"""
        return {
            "success": True,
            "current_step": "refactor",
            "next_step": "complete",
            "checklist": [
                "✅ Test is passing (Green)",
                "✅ Improve code quality",
                "✅ Remove duplication",
                "✅ Add documentation",
                "✅ Run tests frequently",
                "✅ Keep tests green"
            ],
            "guidance": "Refactor code for clarity and maintainability. Tests should stay green!",
            "refactoring_checklist": [
                "Extract methods/functions",
                "Improve variable names",
                "Add type hints (Python) or types (TypeScript)",
                "Add docstrings/comments",
                "Remove dead code",
                "Optimize performance if needed"
            ]
        }
    
    def _get_backend_test_template(self, feature: str) -> str:
        """Generate backend test template"""
        return f'''"""
Test for {feature}
Following TDD workflow
"""

import pytest
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_{feature.lower().replace(" ", "_")}():
    """
    Test: {feature}
    
    Red Phase: This test should FAIL initially
    """
    # Arrange
    payload = {{
        "test": "data"
    }}
    
    # Act
    response = client.post("/api/endpoint", json=payload)
    
    # Assert
    assert response.status_code == 200
    assert "expected_key" in response.json()
    
    # TODO: Add more assertions based on feature requirements


@pytest.mark.asyncio
async def test_{feature.lower().replace(" ", "_")}_edge_cases():
    """Test edge cases"""
    # Test with invalid data
    response = client.post("/api/endpoint", json={{}})
    assert response.status_code == 400
'''
    
    def _get_frontend_test_template(self, feature: str) -> str:
        """Generate frontend test template"""
        return f'''/**
 * Test for {feature}
 * Following TDD workflow
 */

import {{ render, screen, fireEvent, waitFor }} from '@testing-library/react';
import {{ ComponentName }} from './ComponentName';

describe('{feature}', () => {{
  test('should render correctly', () => {{
    // Arrange
    render(<ComponentName />);
    
    // Act
    const element = screen.getByText(/expected text/i);
    
    // Assert
    expect(element).toBeInTheDocument();
  }});
  
  test('should handle user interaction', async () => {{
    // Arrange
    render(<ComponentName />);
    
    // Act
    const button = screen.getByRole('button', {{ name: /submit/i }});
    fireEvent.click(button);
    
    // Assert
    await waitFor(() => {{
      expect(screen.getByText(/success/i)).toBeInTheDocument();
    }});
  }});
}});
'''
    
    def _get_e2e_test_template(self, feature: str) -> str:
        """Generate E2E test template"""
        return f'''"""
E2E Test for {feature}
Using Playwright
"""

import pytest
from playwright.async_api import Page, expect


@pytest.mark.asyncio
async def test_{feature.lower().replace(" ", "_")}_e2e(page: Page):
    """
    E2E Test: {feature}
    
    Tests full user workflow
    """
    # Navigate to page
    await page.goto("http://localhost:3000")
    
    # Perform actions
    await page.click("text=Button")
    await page.fill("input[name='field']", "test value")
    await page.click("button[type='submit']")
    
    # Verify results
    await expect(page.locator(".success-message")).to_be_visible()
    await expect(page.locator(".result")).to_contain_text("Expected Result")
'''
