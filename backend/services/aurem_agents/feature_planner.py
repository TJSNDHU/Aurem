"""
AUREM Feature Planner Agent
Plans new features with DB/API/UI architecture
Inspired by ECC's planner agent
"""

from typing import Dict, Any, List
import logging

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AUREMFeaturePlanner(BaseAgent):
    """
    Agent that creates implementation plans for new features
    
    Capabilities:
    1. Break down features into tasks
    2. Design database schema
    3. Plan API endpoints
    4. Design UI components
    5. Estimate complexity and time
    """
    
    def __init__(self):
        super().__init__(
            name="aurem-feature-planner",
            description="Plans new AUREM features with architecture design"
        )
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute feature planning
        
        Context parameters:
        - feature_description: str (what to build)
        - feature_type: "connector" | "subscription" | "admin" | "api" | "ui" | "full_stack"
        - complexity: "simple" | "medium" | "complex" | "auto"
        
        Returns:
        - success: bool
        - plan: dict (implementation plan)
        - tasks: list (breakdown of tasks)
        - estimate: dict (time and complexity estimates)
        """
        feature_description = context.get("feature_description")
        feature_type = context.get("feature_type", "full_stack")
        complexity = context.get("complexity", "auto")
        
        if not feature_description:
            return {
                "success": False,
                "message": "feature_description is required"
            }
        
        logger.info(f"[Planner] Planning feature: {feature_description}")
        
        # Auto-detect feature type if not specified
        if feature_type == "auto":
            feature_type = self._detect_feature_type(feature_description)
        
        # Generate plan based on type
        if feature_type == "connector":
            plan = self._plan_connector(feature_description)
        elif feature_type == "subscription":
            plan = self._plan_subscription_feature(feature_description)
        elif feature_type == "admin":
            plan = self._plan_admin_feature(feature_description)
        elif feature_type == "api":
            plan = self._plan_api_feature(feature_description)
        elif feature_type == "ui":
            plan = self._plan_ui_feature(feature_description)
        else:  # full_stack
            plan = self._plan_full_stack_feature(feature_description)
        
        # Auto-detect complexity if needed
        if complexity == "auto":
            complexity = self._estimate_complexity(plan)
        
        plan["complexity"] = complexity
        plan["estimate"] = self._estimate_time(plan, complexity)
        
        return {
            "success": True,
            "feature": feature_description,
            "feature_type": feature_type,
            "plan": plan
        }
    
    def _detect_feature_type(self, description: str) -> str:
        """Auto-detect feature type from description"""
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ["slack", "twitter", "discord", "connector", "integration"]):
            return "connector"
        elif any(word in desc_lower for word in ["subscription", "payment", "billing", "plan"]):
            return "subscription"
        elif any(word in desc_lower for word in ["admin", "dashboard", "analytics", "metrics"]):
            return "admin"
        elif any(word in desc_lower for word in ["api", "endpoint", "route"]):
            return "api"
        elif any(word in desc_lower for word in ["ui", "component", "page", "form"]):
            return "ui"
        else:
            return "full_stack"
    
    def _plan_connector(self, description: str) -> Dict[str, Any]:
        """Plan a new connector"""
        # Extract platform name
        platforms = ["slack", "discord", "twitter", "telegram", "notion", "linear", "jira"]
        platform = next((p for p in platforms if p in description.lower()), "custom")
        
        return {
            "type": "connector",
            "platform": platform,
            "database_changes": [
                {
                    "collection": "connector_credentials",
                    "fields": [
                        {"name": "user_id", "type": "string", "required": True},
                        {"name": "platform", "type": "string", "value": platform},
                        {"name": "credentials", "type": "object", "encrypted": True},
                        {"name": "created_at", "type": "datetime"},
                        {"name": "expires_at", "type": "datetime", "required": False}
                    ]
                },
                {
                    "collection": "connector_data",
                    "fields": [
                        {"name": "platform", "type": "string"},
                        {"name": "data", "type": "object"},
                        {"name": "fetched_at", "type": "datetime"}
                    ]
                }
            ],
            "backend_tasks": [
                {
                    "task": f"Create {platform.capitalize()}Connector class",
                    "file": "services/connector_ecosystem.py",
                    "methods": ["authenticate", "fetch", "post"],
                    "priority": "high"
                },
                {
                    "task": f"Register {platform} in ConnectorEcosystem",
                    "file": "services/connector_ecosystem.py",
                    "code": f'"{platform}": {platform.capitalize()}Connector()',
                    "priority": "high"
                },
                {
                    "task": f"Add {platform} to connector router",
                    "file": "routers/connector_router.py",
                    "priority": "medium"
                },
                {
                    "task": f"Write tests for {platform} connector",
                    "file": f"tests/test_{platform}_connector.py",
                    "priority": "high"
                }
            ],
            "api_endpoints": [
                {
                    "method": "POST",
                    "path": "/api/connectors/connect",
                    "body": {"platform": platform, "credentials": "object"},
                    "description": f"Connect {platform} account"
                },
                {
                    "method": "POST",
                    "path": "/api/connectors/fetch",
                    "body": {"platform": platform, "query": "object"},
                    "description": f"Fetch data from {platform}"
                },
                {
                    "method": "POST",
                    "path": "/api/connectors/post",
                    "body": {"platform": platform, "content": "object"},
                    "description": f"Post to {platform}"
                }
            ],
            "frontend_tasks": [
                {
                    "task": f"Create {platform.capitalize()}ConnectorCard component",
                    "file": f"src/components/connectors/{platform.capitalize()}Card.jsx",
                    "priority": "medium"
                },
                {
                    "task": f"Add {platform} to Connectors page",
                    "file": "src/platform/Connectors.jsx",
                    "priority": "medium"
                }
            ],
            "documentation": [
                f"Update CONNECTOR_IMPLEMENTATION_STATUS.md",
                f"Create {platform.upper()}_SETUP.md with API key instructions"
            ]
        }
    
    def _plan_subscription_feature(self, description: str) -> Dict[str, Any]:
        """Plan subscription/billing feature"""
        return {
            "type": "subscription",
            "database_changes": [
                {
                    "collection": "subscription_plans",
                    "modifications": "Describe changes needed"
                },
                {
                    "collection": "user_subscriptions",
                    "modifications": "Describe changes needed"
                }
            ],
            "backend_tasks": [
                {
                    "task": "Update subscription models",
                    "file": "models/subscription_models.py",
                    "priority": "high"
                },
                {
                    "task": "Update subscription router",
                    "file": "routers/subscription_public_router.py",
                    "priority": "high"
                },
                {
                    "task": "Update TOON service if needed",
                    "file": "services/toon_service.py",
                    "priority": "medium"
                }
            ],
            "api_endpoints": [
                {
                    "method": "POST",
                    "path": "/api/subscriptions/...",
                    "description": "New subscription endpoint"
                }
            ],
            "frontend_tasks": [
                {
                    "task": "Update subscription UI",
                    "file": "src/platform/Subscriptions.jsx",
                    "priority": "high"
                }
            ]
        }
    
    def _plan_admin_feature(self, description: str) -> Dict[str, Any]:
        """Plan admin feature"""
        return {
            "type": "admin",
            "backend_tasks": [
                {
                    "task": "Create admin endpoint",
                    "file": "routers/admin_mission_control_router.py",
                    "priority": "high"
                },
                {
                    "task": "Add admin authentication check",
                    "priority": "high"
                }
            ],
            "frontend_tasks": [
                {
                    "task": "Create admin component",
                    "file": "src/platform/admin/...",
                    "priority": "high"
                },
                {
                    "task": "Add to Admin Mission Control",
                    "file": "src/platform/AdminMissionControl.jsx",
                    "priority": "medium"
                }
            ]
        }
    
    def _plan_api_feature(self, description: str) -> Dict[str, Any]:
        """Plan API-only feature"""
        return {
            "type": "api",
            "backend_tasks": [
                {
                    "task": "Create new router",
                    "file": "routers/new_feature_router.py",
                    "priority": "high"
                },
                {
                    "task": "Create Pydantic models",
                    "file": "models/new_feature_models.py",
                    "priority": "high"
                },
                {
                    "task": "Create service layer if needed",
                    "file": "services/new_feature_service.py",
                    "priority": "medium"
                },
                {
                    "task": "Register router in server.py",
                    "file": "server.py",
                    "priority": "high"
                }
            ]
        }
    
    def _plan_ui_feature(self, description: str) -> Dict[str, Any]:
        """Plan UI-only feature"""
        return {
            "type": "ui",
            "frontend_tasks": [
                {
                    "task": "Create component",
                    "file": "src/components/...",
                    "priority": "high"
                },
                {
                    "task": "Add route if needed",
                    "file": "src/App.js",
                    "priority": "medium"
                },
                {
                    "task": "Style with Shadcn UI",
                    "priority": "medium"
                }
            ]
        }
    
    def _plan_full_stack_feature(self, description: str) -> Dict[str, Any]:
        """Plan full-stack feature"""
        return {
            "type": "full_stack",
            "phases": [
                {
                    "phase": 1,
                    "name": "Database Schema",
                    "tasks": ["Design MongoDB collections", "Define indexes"]
                },
                {
                    "phase": 2,
                    "name": "Backend API",
                    "tasks": ["Create models", "Create router", "Create service", "Write tests"]
                },
                {
                    "phase": 3,
                    "name": "Frontend UI",
                    "tasks": ["Create components", "Add routing", "Connect to API"]
                },
                {
                    "phase": 4,
                    "name": "Testing & Documentation",
                    "tasks": ["E2E tests", "Update docs", "Security review"]
                }
            ],
            "database_changes": ["To be designed"],
            "backend_tasks": ["To be planned"],
            "frontend_tasks": ["To be planned"],
            "testing_tasks": ["Unit tests", "Integration tests", "E2E tests"]
        }
    
    def _estimate_complexity(self, plan: Dict) -> str:
        """Estimate feature complexity"""
        task_count = 0
        
        if "backend_tasks" in plan:
            task_count += len(plan["backend_tasks"])
        if "frontend_tasks" in plan:
            task_count += len(plan["frontend_tasks"])
        if "database_changes" in plan:
            task_count += len(plan["database_changes"])
        
        if task_count <= 3:
            return "simple"
        elif task_count <= 7:
            return "medium"
        else:
            return "complex"
    
    def _estimate_time(self, plan: Dict, complexity: str) -> Dict[str, Any]:
        """Estimate implementation time"""
        # Base estimates (in hours)
        estimates = {
            "simple": {"min": 2, "max": 4},
            "medium": {"min": 4, "max": 8},
            "complex": {"min": 8, "max": 16}
        }
        
        base = estimates.get(complexity, estimates["medium"])
        
        # Adjust for feature type
        multiplier = 1.0
        
        if plan.get("type") == "connector":
            multiplier = 1.2  # Connectors need integration testing
        elif plan.get("type") == "subscription":
            multiplier = 1.5  # Payment features need extra security
        elif plan.get("type") == "full_stack":
            multiplier = 2.0  # Full stack takes longer
        
        return {
            "min_hours": int(base["min"] * multiplier),
            "max_hours": int(base["max"] * multiplier),
            "complexity": complexity,
            "note": "Estimates include development, testing, and documentation"
        }
