"""
TOON (Token-Oriented Object Notation) Encoder
Reduces JSON token usage by 30-60% for LLM prompts

Formats:
1. Tabular TOON: Type[count]{key1, key2}: val1, val2; val3, val4
2. Indentation TOON: Uses indentation instead of braces for nested objects
3. Compact Primitives: true→T, false→F, null→N
"""

import json
from typing import Any, List, Dict, Union, Optional
from collections import OrderedDict


class ToonEncoder:
    """
    TOON Encoder - Convert JSON to Token-Oriented Object Notation
    Optimized for LLM context efficiency
    """
    
    def __init__(self, indent_size: int = 2, max_inline_length: int = 80):
        self.indent_size = indent_size
        self.max_inline_length = max_inline_length
    
    def encode(self, data: Any, type_hint: str = None) -> str:
        """
        Encode data to TOON format
        
        Args:
            data: JSON-compatible data (dict, list, primitives)
            type_hint: Optional type name for arrays (e.g., "Product", "Formula")
        
        Returns:
            TOON-formatted string
        """
        if data is None:
            return "N"
        
        if isinstance(data, bool):
            return "T" if data else "F"
        
        if isinstance(data, (int, float)):
            return str(data)
        
        if isinstance(data, str):
            # Only quote if contains special characters
            if any(c in data for c in [',', ';', ':', '\n', '{', '}', '[', ']']):
                return f'"{data}"'
            return data
        
        if isinstance(data, list):
            return self._encode_array(data, type_hint)
        
        if isinstance(data, dict):
            return self._encode_object(data)
        
        return str(data)
    
    def _encode_array(self, arr: List, type_hint: str = None) -> str:
        """Encode array - uses tabular format for uniform objects"""
        if not arr:
            return "[]"
        
        # Check if all items are dicts with same keys (uniform array)
        if all(isinstance(item, dict) for item in arr):
            keys = self._get_common_keys(arr)
            if keys and len(keys) >= 2:
                return self._encode_tabular(arr, keys, type_hint)
        
        # Check if all items are primitives
        if all(isinstance(item, (str, int, float, bool, type(None))) for item in arr):
            values = [self.encode(item) for item in arr]
            inline = ", ".join(values)
            if len(inline) <= self.max_inline_length:
                return f"[{inline}]"
        
        # Fall back to line-by-line
        lines = [self.encode(item) for item in arr]
        return "[\n  " + "\n  ".join(lines) + "\n]"
    
    def _encode_tabular(self, arr: List[Dict], keys: List[str], type_hint: str = None) -> str:
        """
        Encode uniform array as tabular TOON
        Format: Type[count]{key1, key2}: val1, val2; val3, val4
        """
        type_name = type_hint or "Item"
        count = len(arr)
        
        # Header
        header = f"{type_name}[{count}]{{{', '.join(keys)}}}"
        
        # Values
        rows = []
        for item in arr:
            values = []
            for key in keys:
                val = item.get(key)
                encoded = self._encode_value_compact(val)
                values.append(encoded)
            rows.append(", ".join(values))
        
        # Check if fits inline
        inline_values = "; ".join(rows)
        if len(header) + len(inline_values) + 2 <= self.max_inline_length * 2:
            return f"{header}: {inline_values}"
        
        # Multi-line format
        return f"{header}:\n  " + "\n  ".join(rows)
    
    def _encode_object(self, obj: Dict, indent: int = 0) -> str:
        """Encode object using indentation-based TOON"""
        if not obj:
            return "{}"
        
        lines = []
        prefix = " " * indent
        
        for key, value in obj.items():
            if isinstance(value, dict) and value:
                # Nested object - use indentation
                nested = self._encode_object(value, indent + self.indent_size)
                lines.append(f"{prefix}{key}:")
                lines.append(nested)
            elif isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
                # Array of objects - use tabular
                tabular = self._encode_tabular(value, self._get_common_keys(value), key.rstrip('s').title())
                lines.append(f"{prefix}{key}: {tabular}")
            else:
                # Simple value
                encoded = self.encode(value)
                lines.append(f"{prefix}{key}: {encoded}")
        
        return "\n".join(lines)
    
    def _encode_value_compact(self, val: Any) -> str:
        """Encode a single value compactly for tabular rows"""
        if val is None:
            return "N"
        if isinstance(val, bool):
            return "T" if val else "F"
        if isinstance(val, (int, float)):
            # Round floats to 2 decimals
            if isinstance(val, float):
                return f"{val:.2f}".rstrip('0').rstrip('.')
            return str(val)
        if isinstance(val, str):
            # Truncate long strings
            if len(val) > 50:
                return val[:47] + "..."
            if any(c in val for c in [',', ';', ':']):
                return f'"{val}"'
            return val
        if isinstance(val, list):
            if not val:
                return "[]"
            items = [self._encode_value_compact(v) for v in val[:5]]
            result = "|".join(items)
            if len(val) > 5:
                result += f"|+{len(val)-5}"
            return f"[{result}]"
        if isinstance(val, dict):
            # Compact dict representation
            items = [f"{k}={self._encode_value_compact(v)}" for k, v in list(val.items())[:3]]
            return "{" + ",".join(items) + "}"
        return str(val)
    
    def _get_common_keys(self, arr: List[Dict]) -> Optional[List[str]]:
        """Get common keys across all dicts in array (for tabular format)"""
        if not arr or not all(isinstance(item, dict) for item in arr):
            return None
        
        # Get keys from first item
        first_keys = set(arr[0].keys())
        
        # Check if all items have at least 80% of these keys
        common_keys = first_keys.copy()
        for item in arr[1:]:
            item_keys = set(item.keys())
            common_keys &= item_keys
        
        if len(common_keys) >= len(first_keys) * 0.6:
            # Return in original order
            return [k for k in arr[0].keys() if k in common_keys]
        
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# SPECIALIZED ENCODERS FOR REROOTS DATA
# ═══════════════════════════════════════════════════════════════════════════════

class ReRootsToonEncoder(ToonEncoder):
    """
    Specialized TOON encoder for ReRoots skincare data
    Optimized for formulas, products, and inventory
    """
    
    # Field abbreviations for common skincare terms
    FIELD_ABBREV = {
        'ingredient': 'ing',
        'percentage': 'pct',
        'concentration': 'conc',
        'function': 'fn',
        'description': 'desc',
        'benefits': 'ben',
        'price': 'pr',
        'stock': 'stk',
        'quantity': 'qty',
        'product_id': 'pid',
        'product_name': 'pname',
        'category': 'cat',
        'created_at': 'crt',
        'updated_at': 'upd',
        'is_active': 'act',
        'hero_ingredients': 'hero',
        'primary_benefit': 'pbf',
        'application_method': 'app',
        'skin_types': 'skin',
        'concerns': 'cnc',
    }
    
    def encode_formula(self, formula: Dict) -> str:
        """
        Encode skincare formula for LLM analysis
        
        Input: {name: "Aura-Gen", ingredients: [{ingredient: "Water", percentage: 60, function: "Base"}, ...]}
        Output: Formula[Aura-Gen]:
                  Ingredient[12]{ing, pct, fn}: Water, 60, Base; PDRN, 5, Repair; ...
        """
        name = formula.get('name', 'Unknown')
        ingredients = formula.get('ingredients', [])
        
        lines = [f"Formula[{name}]:"]
        
        if ingredients:
            # Use tabular for ingredients
            keys = ['ingredient', 'percentage', 'function']
            abbrev_keys = [self.FIELD_ABBREV.get(k, k) for k in keys]
            
            header = f"  Ing[{len(ingredients)}]{{{', '.join(abbrev_keys)}}}"
            
            rows = []
            for ing in ingredients:
                values = [
                    str(ing.get('ingredient', ing.get('name', 'N/A'))),
                    str(ing.get('percentage', ing.get('concentration', 'N/A'))),
                    str(ing.get('function', ing.get('benefit', 'N/A')))
                ]
                rows.append(", ".join(values))
            
            lines.append(f"{header}: {'; '.join(rows)}")
        
        # Add other formula metadata
        for key in ['ph_level', 'texture', 'absorption_rate', 'shelf_life']:
            if key in formula:
                lines.append(f"  {key}: {formula[key]}")
        
        return "\n".join(lines)
    
    def encode_products(self, products: List[Dict]) -> str:
        """
        Encode product catalog for LLM
        
        Reduces: [{name: "Serum A", price: 89, stock: 50, ...}, ...]
        To: Product[10]{name, pr, stk, cat}: Serum A, 89, 50, Serum; ...
        """
        if not products:
            return "Products: []"
        
        # Key fields for products
        keys = ['name', 'price', 'stock', 'category']
        abbrev_keys = [self.FIELD_ABBREV.get(k, k) for k in keys]
        
        header = f"Product[{len(products)}]{{{', '.join(abbrev_keys)}}}"
        
        rows = []
        for p in products:
            values = [
                str(p.get('name', 'N/A'))[:30],
                str(p.get('price', 0)),
                str(p.get('stock', p.get('quantity', 0))),
                str(p.get('category', p.get('type', 'N/A')))[:15]
            ]
            rows.append(", ".join(values))
        
        if len("; ".join(rows)) < 200:
            return f"{header}: {'; '.join(rows)}"
        
        return f"{header}:\n  " + "\n  ".join(rows)
    
    def encode_inventory(self, inventory: List[Dict]) -> str:
        """
        Encode inventory/stock data for LLM
        
        Reduces daily stock logs to compact format
        """
        if not inventory:
            return "Inventory: []"
        
        keys = ['sku', 'name', 'qty', 'reorder', 'status']
        
        header = f"Stock[{len(inventory)}]{{{', '.join(keys)}}}"
        
        rows = []
        for item in inventory:
            qty = item.get('quantity', item.get('stock', 0))
            reorder = item.get('reorder_point', item.get('min_stock', 10))
            status = "LOW" if qty < reorder else "OK"
            
            values = [
                str(item.get('sku', item.get('id', 'N/A')))[:10],
                str(item.get('name', 'N/A'))[:20],
                str(qty),
                str(reorder),
                status
            ]
            rows.append(", ".join(values))
        
        return f"{header}:\n  " + "\n  ".join(rows)
    
    def encode_customer(self, customer: Dict) -> str:
        """Encode customer data compactly"""
        lines = [f"Customer[{customer.get('id', 'N/A')}]:"]
        
        # Core info
        lines.append(f"  name: {customer.get('name', 'N/A')}")
        lines.append(f"  tier: {customer.get('tier', 'Silver')}")
        lines.append(f"  pts: {customer.get('points', 0)}")
        
        # Order history summary
        orders = customer.get('orders', [])
        if orders:
            total = sum(o.get('total', 0) for o in orders)
            lines.append(f"  orders: {len(orders)}, total: ${total:.2f}")
        
        # Skin profile
        skin = customer.get('skin_profile', {})
        if skin:
            profile = f"{skin.get('type', 'N/A')}, concerns: {', '.join(skin.get('concerns', []))}"
            lines.append(f"  skin: {profile}")
        
        return "\n".join(lines)
    
    def encode_order(self, order: Dict) -> str:
        """Encode order data compactly"""
        items = order.get('items', [])
        items_str = "; ".join([
            f"{i.get('name', 'Item')}x{i.get('quantity', 1)}"
            for i in items[:5]
        ])
        if len(items) > 5:
            items_str += f" +{len(items)-5} more"
        
        return (
            f"Order[{order.get('id', 'N/A')}]: "
            f"${order.get('total', 0):.2f}, "
            f"status: {order.get('status', 'pending')}, "
            f"items: [{items_str}]"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSION UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def json_to_toon(data: Any, data_type: str = None) -> str:
    """
    Convert JSON data to TOON format
    
    Args:
        data: JSON-compatible data
        data_type: Hint for data type ('formula', 'products', 'inventory', 'customer', 'order', or None for generic)
    
    Returns:
        TOON-formatted string
    """
    encoder = ReRootsToonEncoder()
    
    if data_type == 'formula':
        return encoder.encode_formula(data)
    elif data_type == 'products':
        return encoder.encode_products(data if isinstance(data, list) else [data])
    elif data_type == 'inventory':
        return encoder.encode_inventory(data if isinstance(data, list) else [data])
    elif data_type == 'customer':
        return encoder.encode_customer(data)
    elif data_type == 'order':
        return encoder.encode_order(data)
    else:
        return encoder.encode(data)


def toon_to_json(toon_str: str) -> Dict:
    """
    Parse TOON back to JSON (basic implementation)
    For when you need to convert TOON responses back to structured data
    """
    # This is a simplified parser - full implementation would need proper grammar
    result = {}
    
    lines = toon_str.strip().split('\n')
    current_key = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Handle tabular format
            if '[' in key and '{' in key:
                # Parse Type[count]{keys}: values format
                # This would need more complex parsing
                result[key.split('[')[0].lower()] = value
            else:
                # Simple key: value
                if value == 'T':
                    result[key] = True
                elif value == 'F':
                    result[key] = False
                elif value == 'N':
                    result[key] = None
                elif value.isdigit():
                    result[key] = int(value)
                elif value.replace('.', '').isdigit():
                    result[key] = float(value)
                else:
                    result[key] = value
    
    return result


def estimate_token_savings(json_data: Any, data_type: str = None) -> Dict:
    """
    Estimate token savings from TOON conversion
    
    Returns:
        {
            json_chars: int,
            toon_chars: int,
            savings_percent: float,
            estimated_tokens_saved: int
        }
    """
    json_str = json.dumps(json_data, separators=(',', ':'))
    toon_str = json_to_toon(json_data, data_type)
    
    json_chars = len(json_str)
    toon_chars = len(toon_str)
    
    # Rough estimate: 4 chars per token
    json_tokens = json_chars / 4
    toon_tokens = toon_chars / 4
    
    savings_percent = ((json_chars - toon_chars) / json_chars) * 100 if json_chars > 0 else 0
    
    return {
        'json_chars': json_chars,
        'toon_chars': toon_chars,
        'savings_percent': round(savings_percent, 1),
        'estimated_tokens_saved': int(json_tokens - toon_tokens)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE FOR MONGODB
# ═══════════════════════════════════════════════════════════════════════════════

class ToonMiddleware:
    """
    Middleware to automatically convert MongoDB outputs to TOON
    """
    
    def __init__(self, db=None):
        self.db = db
        self.encoder = ReRootsToonEncoder()
    
    def set_db(self, db):
        self.db = db
    
    async def get_products_toon(self, query: Dict = None, limit: int = 50) -> str:
        """Fetch products and return as TOON"""
        if self.db is None:
            return "Products: []"
        
        products = await self.db.products.find(
            query or {},
            {'_id': 0, 'name': 1, 'price': 1, 'stock': 1, 'category': 1, 'slug': 1}
        ).limit(limit).to_list(limit)
        
        return self.encoder.encode_products(products)
    
    async def get_inventory_toon(self, low_stock_only: bool = False) -> str:
        """Fetch inventory and return as TOON"""
        if self.db is None:
            return "Inventory: []"
        
        query = {'stock': {'$lt': 10}} if low_stock_only else {}
        
        items = await self.db.products.find(
            query,
            {'_id': 0, 'sku': 1, 'name': 1, 'stock': 1, 'reorder_point': 1}
        ).to_list(100)
        
        return self.encoder.encode_inventory(items)
    
    async def get_customer_toon(self, customer_id: str) -> str:
        """Fetch customer and return as TOON"""
        if self.db is None:
            return "Customer: N/A"
        
        customer = await self.db.users.find_one(
            {'id': customer_id},
            {'_id': 0}
        )
        
        if not customer:
            return "Customer: N/A"
        
        return self.encoder.encode_customer(customer)
    
    async def get_formula_toon(self, product_id: str) -> str:
        """Fetch product formula and return as TOON"""
        if self.db is None:
            return "Formula: N/A"
        
        product = await self.db.products.find_one(
            {'id': product_id},
            {'_id': 0, 'name': 1, 'ingredients': 1, 'hero_ingredients': 1}
        )
        
        if not product:
            return "Formula: N/A"
        
        # Build formula structure
        formula = {
            'name': product.get('name'),
            'ingredients': product.get('hero_ingredients', [])
        }
        
        return self.encoder.encode_formula(formula)


# Global middleware instance
toon_middleware = ToonMiddleware()


def get_toon_middleware():
    """Get the global TOON middleware instance"""
    return toon_middleware
