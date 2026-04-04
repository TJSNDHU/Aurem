"""
Generative UI Component Generator
LLM-powered service to generate React components dynamically
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ComponentGenerator:
    """
    Generate React components using LLM
    
    Converts data + intent → Interactive UI components
    """
    
    def __init__(self):
        self.templates = {
            "line_chart": self._line_chart_template,
            "bar_chart": self._bar_chart_template,
            "pie_chart": self._pie_chart_template,
            "metric_card": self._metric_card_template,
            "data_table": self._data_table_template,
            "form": self._form_template
        }
        
        logger.info("[GenUI] Component Generator initialized")
    
    def generate_component(self, component_type: str, data: Any, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate a component from data
        
        Args:
            component_type: Type of component (line_chart, pie_chart, metric_card, etc.)
            data: Data to visualize
            config: Optional configuration (title, colors, etc.)
        
        Returns:
            Component spec with props and data
        """
        try:
            if component_type not in self.templates:
                raise ValueError(f"Unknown component type: {component_type}")
            
            config = config or {}
            
            # Call template function
            component_spec = self.templates[component_type](data, config)
            
            return {
                "success": True,
                "component_type": component_type,
                "spec": component_spec
            }
        
        except Exception as e:
            logger.error(f"[GenUI] Component generation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _line_chart_template(self, data: List[Dict], config: Dict) -> Dict:
        """
        Generate line chart component spec
        
        Expected data format:
        [
            {"date": "2024-01", "value": 1200},
            {"date": "2024-02", "value": 1500}
        ]
        """
        return {
            "component": "LineChart",
            "props": {
                "data": data,
                "xKey": config.get("xKey", "date"),
                "yKey": config.get("yKey", "value"),
                "title": config.get("title", "Line Chart"),
                "color": config.get("color", "#8884d8"),
                "height": config.get("height", 300),
                "showGrid": config.get("showGrid", True),
                "showTooltip": config.get("showTooltip", True)
            }
        }
    
    def _bar_chart_template(self, data: List[Dict], config: Dict) -> Dict:
        """
        Generate bar chart component spec
        """
        return {
            "component": "BarChart",
            "props": {
                "data": data,
                "xKey": config.get("xKey", "name"),
                "yKey": config.get("yKey", "value"),
                "title": config.get("title", "Bar Chart"),
                "color": config.get("color", "#82ca9d"),
                "height": config.get("height", 300)
            }
        }
    
    def _pie_chart_template(self, data: List[Dict], config: Dict) -> Dict:
        """
        Generate pie chart component spec
        
        Expected data format:
        [
            {"name": "Free", "value": 100},
            {"name": "Starter", "value": 50}
        ]
        """
        return {
            "component": "PieChart",
            "props": {
                "data": data,
                "nameKey": config.get("nameKey", "name"),
                "valueKey": config.get("valueKey", "value"),
                "title": config.get("title", "Distribution"),
                "colors": config.get("colors", ["#0088FE", "#00C49F", "#FFBB28", "#FF8042"]),
                "height": config.get("height", 300)
            }
        }
    
    def _metric_card_template(self, data: Dict, config: Dict) -> Dict:
        """
        Generate metric card component spec
        
        Expected data format:
        {
            "value": 1234,
            "label": "Total Revenue",
            "change": "+12%",
            "trend": "up"
        }
        """
        return {
            "component": "MetricCard",
            "props": {
                "value": data.get("value"),
                "label": data.get("label", "Metric"),
                "change": data.get("change"),
                "trend": data.get("trend", "neutral"),
                "icon": config.get("icon"),
                "color": config.get("color", "blue")
            }
        }
    
    def _data_table_template(self, data: List[Dict], config: Dict) -> Dict:
        """
        Generate data table component spec
        
        Expected data format:
        [
            {"id": 1, "name": "John", "email": "john@example.com"},
            {"id": 2, "name": "Jane", "email": "jane@example.com"}
        ]
        """
        # Auto-detect columns from first row
        columns = []
        if data and len(data) > 0:
            first_row = data[0]
            for key in first_row.keys():
                columns.append({
                    "key": key,
                    "label": key.replace("_", " ").title()
                })
        
        return {
            "component": "DataTable",
            "props": {
                "data": data,
                "columns": config.get("columns", columns),
                "title": config.get("title", "Data Table"),
                "searchable": config.get("searchable", True),
                "sortable": config.get("sortable", True),
                "pageSize": config.get("pageSize", 10)
            }
        }
    
    def _form_template(self, data: Dict, config: Dict) -> Dict:
        """
        Generate form component spec
        
        Expected data format:
        {
            "fields": [
                {"name": "email", "type": "email", "label": "Email", "required": true},
                {"name": "message", "type": "textarea", "label": "Message"}
            ],
            "submitLabel": "Send"
        }
        """
        return {
            "component": "DynamicForm",
            "props": {
                "fields": data.get("fields", []),
                "title": config.get("title", "Form"),
                "submitLabel": data.get("submitLabel", "Submit"),
                "onSubmit": config.get("onSubmit")
            }
        }
    
    def generate_dashboard(self, components: List[Dict]) -> Dict[str, Any]:
        """
        Generate a complete dashboard with multiple components
        
        Args:
            components: List of component specs
        
        Returns:
            Dashboard layout with all components
        """
        try:
            dashboard_components = []
            
            for comp_def in components:
                component_type = comp_def.get("type")
                data = comp_def.get("data")
                config = comp_def.get("config", {})
                
                result = self.generate_component(component_type, data, config)
                
                if result.get("success"):
                    dashboard_components.append(result["spec"])
            
            return {
                "success": True,
                "dashboard": {
                    "components": dashboard_components,
                    "layout": "grid",
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        
        except Exception as e:
            logger.error(f"[GenUI] Dashboard generation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
_component_generator = None


def get_component_generator() -> ComponentGenerator:
    """Get singleton ComponentGenerator instance"""
    global _component_generator
    
    if _component_generator is None:
        _component_generator = ComponentGenerator()
    
    return _component_generator
