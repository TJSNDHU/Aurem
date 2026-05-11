"""
Connector Pattern Skill
Template and guide for building new AUREM connectors
"""

from typing import Dict, Any, List
import logging

from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class ConnectorPatternSkill(BaseSkill):
    """
    Connector Pattern workflow
    
    Provides:
    - Connector class template
    - Implementation checklist
    - Best practices
    - Testing guide
    """
    
    def __init__(self):
        super().__init__(
            name="connector-pattern",
            description="Template and guide for building AUREM connectors",
            category="development"
        )
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute connector pattern workflow
        
        Context:
        {
            "platform": "Discord",
            "features": ["send_message", "fetch_messages", "manage_channels"],
            "auth_type": "token" | "oauth" | "api_key"
        }
        
        Returns:
        {
            "success": True,
            "template_code": "...",
            "checklist": [...],
            "testing_guide": "...",
            "best_practices": [...]
        }
        """
        platform = context.get("platform", "CustomPlatform")
        features = context.get("features", ["authenticate", "fetch", "post"])
        auth_type = context.get("auth_type", "token")
        
        # Generate connector template
        template_code = self._generate_connector_template(platform, features, auth_type)
        
        # Implementation checklist
        checklist = self._get_implementation_checklist(platform)
        
        # Testing guide
        testing_guide = self._get_testing_guide(platform)
        
        # Best practices
        best_practices = self._get_best_practices()
        
        return {
            "success": True,
            "platform": platform,
            "template_code": template_code,
            "checklist": checklist,
            "testing_guide": testing_guide,
            "best_practices": best_practices,
            "next_steps": [
                f"1. Create /app/backend/services/connector_ecosystem.py class for {platform}",
                f"2. Implement authenticate(), fetch(), post() methods",
                f"3. Register in ConnectorEcosystem._initialize_connectors()",
                f"4. Test via /api/connectors/fetch endpoint",
                f"5. Add documentation to CONNECTOR_IMPLEMENTATION_STATUS.md"
            ]
        }
    
    def _generate_connector_template(self, platform: str, features: List[str], auth_type: str) -> str:
        """Generate connector class template"""
        class_name = f"{platform}Connector"
        
        template = f'''class {class_name}:
    """
    {platform} connector
    
    Features:
'''
        
        for feature in features:
            template += f"    - {feature}\n"
        
        template += f'''
    
    Uses: {platform} API
    Requires: {platform.upper()}_API_KEY or credentials
    """
    
    def __init__(self):
        self.authenticated = False
        self.api_key = None
        self.base_url = "https://api.{platform.lower()}.com"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with {platform}
        
        credentials: {{
            "api_key": "..."
        }}
        """
        if credentials and credentials.get("api_key"):
            self.api_key = credentials["api_key"]
            
            # Verify credentials with a lightweight GET on the platform base URL.
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as _c:
                    _r = await _c.get(
                        self.base_url,
                        headers={{"Authorization": f"Bearer {{self.api_key}}"}},
                    )
                    self.authenticated = _r.status_code < 400
                logger.info(
                    "[{platform}] Auth verify HTTP %s → authenticated=%s",
                    _r.status_code, self.authenticated,
                )
                return self.authenticated
            except Exception as e:
                logger.error(f"[{platform}] Auth failed: {{e}}")
                return False
        
        logger.warning("[{platform}] No credentials, using demo mode")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch data from {platform}
        
        query: {{
            "type": "messages" | "users" | "data",
            "limit": 100
        }}
        """
        if not self.authenticated:
            return self._get_demo_data(query)
        
        fetch_type = query.get("type", "messages")
        limit = query.get("limit", 100)
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as _c:
                _r = await _c.get(
                    f"{{self.base_url}}/{{fetch_type}}",
                    headers={{"Authorization": f"Bearer {{self.api_key}}"}},
                    params={{"limit": limit}},
                )
            if _r.status_code >= 400:
                logger.warning(
                    "[{platform}] fetch %s returned HTTP %s — falling back to demo",
                    fetch_type, _r.status_code,
                )
                return self._get_demo_data(query)
            _data = _r.json()
            # Most REST APIs wrap rows under `results` / `data` / `items`.
            return (
                _data.get("results")
                or _data.get("data")
                or _data.get("items")
                or (_data if isinstance(_data, list) else [])
            )
            
        except Exception as e:
            logger.error(f"[{platform}] Fetch error: {{e}}")
            return []
    
    async def post(self, content: Dict) -> bool:
        """
        Post to {platform}
        
        content: {{
            "type": "message",
            "text": "Hello!"
        }}
        """
        if not self.authenticated:
            logger.warning("[{platform}] Not authenticated, simulating post")
            return True
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as _c:
                _r = await _c.post(
                    f"{{self.base_url}}/{{content.get('type', 'post')}}",
                    headers={{
                        "Authorization": f"Bearer {{self.api_key}}",
                        "Content-Type": "application/json",
                    }},
                    json=content,
                )
            logger.info(
                "[{platform}] Post HTTP %s for type=%s",
                _r.status_code, content.get("type", "post"),
            )
            return _r.status_code < 400
            
        except Exception as e:
            logger.error(f"[{platform}] Post error: {{e}}")
            return False
    
    def _get_demo_data(self, query: Dict) -> List[Dict]:
        """Demo data for testing"""
        return [
            {{
                "id": "demo_1",
                "text": "Sample {platform} data",
                "author": "demo_user",
                "created_at": datetime.now(timezone.utc).isoformat()
            }}
        ]
'''
        
        return template
    
    def _get_implementation_checklist(self, platform: str) -> List[Dict]:
        """Get implementation checklist"""
        return [
            {
                "step": 1,
                "task": f"Create {platform}Connector class",
                "status": "pending",
                "details": "Use template above"
            },
            {
                "step": 2,
                "task": "Implement authenticate() method",
                "status": "pending",
                "details": "Handle API keys, tokens, OAuth"
            },
            {
                "step": 3,
                "task": "Implement fetch() method",
                "status": "pending",
                "details": "Support different query types"
            },
            {
                "step": 4,
                "task": "Implement post() method",
                "status": "pending",
                "details": "Support posting content"
            },
            {
                "step": 5,
                "task": "Add demo mode fallback",
                "status": "pending",
                "details": "Works without API keys for testing"
            },
            {
                "step": 6,
                "task": f"Register in ConnectorEcosystem",
                "status": "pending",
                "details": f'Add \"{platform.lower()}\": {platform}Connector() to _initialize_connectors()'
            },
            {
                "step": 7,
                "task": "Test via API",
                "status": "pending",
                "details": "curl -X POST /api/connectors/fetch"
            },
            {
                "step": 8,
                "task": "Add documentation",
                "status": "pending",
                "details": "Update CONNECTOR_IMPLEMENTATION_STATUS.md"
            }
        ]
    
    def _get_testing_guide(self, platform: str) -> str:
        """Get testing guide"""
        return f'''# Testing Guide for {platform} Connector

## 1. Test Authentication
```bash
curl -X POST $API_URL/api/connectors/fetch \\
  -H "Content-Type: application/json" \\
  -d '{{
    "platform": "{platform.lower()}",
    "query": {{"type": "test"}}
  }}'
```

## 2. Test Fetch (Demo Mode)
Should return demo data if not authenticated.

## 3. Test Fetch (Authenticated)
Provide API credentials via Admin Mission Control.

## 4. Test Post
```bash
curl -X POST $API_URL/api/connectors/post \\
  -H "Content-Type: application/json" \\
  -d '{{
    "platform": "{platform.lower()}",
    "content": {{"text": "Test message"}}
  }}'
```

## 5. Verify Error Handling
- Test with invalid credentials
- Test with malformed queries
- Test rate limiting

## 6. Check Logs
```bash
tail -f /var/log/supervisor/backend.*.log | grep {platform}
```
'''
    
    def _get_best_practices(self) -> List[str]:
        """Get best practices"""
        return [
            "✅ Always implement demo mode (works without API keys)",
            "✅ Use async/await for all API calls",
            "✅ Add proper error handling and logging",
            "✅ Never hardcode API keys (use environment variables)",
            "✅ Implement rate limiting awareness",
            "✅ Return consistent data format (List[Dict])",
            "✅ Add authentication verification",
            "✅ Support pagination for large datasets",
            "✅ Cache responses when appropriate",
            "✅ Add comprehensive docstrings",
            "✅ Follow AUREM naming conventions (lowercase platform name)",
            "✅ Test with real API credentials before marking complete"
        ]
