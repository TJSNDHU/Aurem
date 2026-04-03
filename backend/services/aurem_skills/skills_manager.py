"""
AUREM Skills Manager
Central coordinator for all skills
"""

from typing import Dict, Any, Optional, List
import logging

from .tdd_workflow import TDDWorkflowSkill
from .security_review import SecurityReviewSkill
from .connector_pattern import ConnectorPatternSkill

logger = logging.getLogger(__name__)


class SkillsManager:
    """
    Central manager for all AUREM skills
    
    Skills are reusable workflows that can be:
    - Invoked by agents
    - Called via API
    - Triggered by hooks
    """
    
    def __init__(self):
        self.skills = {
            "tdd-workflow": TDDWorkflowSkill(),
            "security-review": SecurityReviewSkill(),
            "connector-pattern": ConnectorPatternSkill()
            # Future skills:
            # "api-design": APIDesignSkill(),
            # "mongo-patterns": MongoDBPatternsSkill(),
            # "frontend-standards": FrontendStandardsSkill(),
            # "admin-workflow": AdminWorkflowSkill(),
            # "integration-guide": IntegrationGuideSkill(),
            # "self-healing-workflow": SelfHealingWorkflowSkill(),
            # "deployment-checklist": DeploymentChecklistSkill()
        }
        
        logger.info(f"[SkillsManager] Initialized with {len(self.skills)} skills")
    
    async def execute_skill(self, skill_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific skill
        
        Args:
            skill_name: Skill identifier (e.g., "tdd-workflow")
            context: Skill-specific parameters
        
        Returns:
            Skill execution result
        """
        skill = self.skills.get(skill_name)
        
        if not skill:
            available_skills = list(self.skills.keys())
            return {
                "success": False,
                "error": f"Unknown skill: {skill_name}",
                "available_skills": available_skills
            }
        
        logger.info(f"[SkillsManager] Executing skill: {skill_name}")
        
        result = await skill.run(context)
        
        return result
    
    def list_skills(self) -> Dict[str, Any]:
        """List all available skills"""
        skills_info = []
        
        for name, skill in self.skills.items():
            skills_info.append(skill.get_info())
        
        # Group by category
        by_category = {}
        for skill_info in skills_info:
            category = skill_info["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(skill_info)
        
        return {
            "total_skills": len(self.skills),
            "skills": skills_info,
            "by_category": by_category
        }
    
    def get_skill_info(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific skill"""
        skill = self.skills.get(skill_name)
        
        if not skill:
            return None
        
        return skill.get_info()


# Global skills manager instance
_skills_manager = SkillsManager()


def get_skills_manager() -> SkillsManager:
    """Get global skills manager instance"""
    return _skills_manager
