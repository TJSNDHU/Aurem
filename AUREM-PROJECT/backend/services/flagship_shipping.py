"""
FlagShip Shipping Integration Service
Provides real-time shipping rates from UPS, FedEx, Purolator, and Canada Post
"""

import httpx
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

# FlagShip API Configuration
FLAGSHIP_API_TOKEN = os.environ.get("FLAGSHIP_API_TOKEN")
FLAGSHIP_API_URL = os.environ.get("FLAGSHIP_API_URL", "https://api.smartship.io")

# ReRoots Store Origin Address (from environment or defaults)
STORE_ORIGIN = {
    "name": os.environ.get("STORE_NAME", "Reroots Aesthetics Inc."),
    "attn": os.environ.get("STORE_ATTN", "Shipping Department"),
    "address": os.environ.get("STORE_ADDRESS", "7221 Sigsbee Drive"),
    "suite": os.environ.get("STORE_SUITE", ""),
    "city": os.environ.get("STORE_CITY", "Mississauga"),
    "state": os.environ.get("STORE_STATE", "ON"),
    "country": os.environ.get("STORE_COUNTRY", "CA"),
    "postal_code": os.environ.get("STORE_POSTAL", "L4T3L6"),
    "phone": os.environ.get("STORE_PHONE", "2265017777"),
    "ext": "",
    "is_commercial": False,
}


# Pydantic Models
class ShippingAddress(BaseModel):
    name: str
    address: str
    city: str
    state: str  # Province code: ON, BC, AB, etc.
    postal_code: str
    country: str = "CA"
    phone: Optional[str] = ""
    is_commercial: bool = False


class Package(BaseModel):
    weight: float = Field(..., description="Weight in kg")
    length: float = Field(default=20, description="Length in cm")
    width: float = Field(default=15, description="Width in cm")
    height: float = Field(default=10, description="Height in cm")
    description: str = "Skincare Products"


class ShippingRate(BaseModel):
    courier_name: str
    courier_code: str
    service_code: str
    service_name: str
    transit_days: int
    estimated_delivery: Optional[str] = None
    base_price: float
    fuel_surcharge: float
    taxes: float
    total_price: float
    currency: str = "CAD"


class ShipmentRequest(BaseModel):
    to_address: ShippingAddress
    packages: List[Package]
    order_id: str
    selected_rate: Optional[ShippingRate] = None


class ShipmentResult(BaseModel):
    shipment_id: str
    tracking_number: str
    label_url: str
    thermal_label_url: Optional[str] = None
    courier_name: str
    service_name: str
    total_cost: float


class FlagShipClient:
    """Async client for FlagShip Shipping API"""

    def __init__(self):
        self.base_url = FLAGSHIP_API_URL
        self.token = FLAGSHIP_API_TOKEN
        self.rate_limit_remaining = 5
        self.rate_limit_reset = datetime.now()

    def _get_headers(self) -> dict:
        """Get authentication headers"""
        return {
            "x-smartship-token": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _handle_rate_limit(self):
        """Handle API rate limiting (1 req/sec, burst of 5)"""
        if self.rate_limit_remaining <= 0:
            wait_time = (self.rate_limit_reset - datetime.now()).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 0.1)
            self.rate_limit_remaining = 5
            self.rate_limit_reset = datetime.now() + timedelta(seconds=1)
        self.rate_limit_remaining -= 1

    async def get_rates(
        self, to_address: ShippingAddress, packages: List[Package]
    ) -> List[ShippingRate]:
        """
        Get shipping rates from all available carriers
        Returns rates sorted by price (cheapest first)
        """
        await self._handle_rate_limit()

        # Prepare request payload
        payload = {
            "from": {
                "name": STORE_ORIGIN["name"],
                "attn": STORE_ORIGIN["attn"],
                "address": STORE_ORIGIN["address"],
                "suite": STORE_ORIGIN["suite"],
                "city": STORE_ORIGIN["city"],
                "state": STORE_ORIGIN["state"],
                "country": STORE_ORIGIN["country"],
                "postal_code": STORE_ORIGIN["postal_code"],
                "phone": STORE_ORIGIN["phone"],
                "is_commercial": STORE_ORIGIN["is_commercial"],
            },
            "to": {
                "name": to_address.name,
                "attn": to_address.name,  # Required by FlagShip API
                "address": to_address.address,
                "city": to_address.city,
                "state": to_address.state,
                "country": to_address.country,
                "postal_code": to_address.postal_code.replace(" ", "").upper(),
                "phone": to_address.phone or "",
                "is_commercial": to_address.is_commercial,
            },
            "packages": {
                "items": [
                    {
                        "weight": max(pkg.weight, 0.45),  # FlagShip minimum 0.45 kg
                        "length": pkg.length,
                        "width": pkg.width,
                        "height": pkg.height,
                        "description": pkg.description,
                    }
                    for pkg in packages
                ],
                "units": "metric",
                "type": "package",
            },
            "payment": {"payer": "F"},  # FlagShip account pays
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/ship/rates",
                    json=payload,
                    headers=self._get_headers(),
                )

                if response.status_code == 429:
                    # Rate limited - wait and retry
                    await asyncio.sleep(2)
                    response = await client.post(
                        f"{self.base_url}/ship/rates",
                        json=payload,
                        headers=self._get_headers(),
                    )

                response.raise_for_status()
                data = response.json()

                # Process rates
                rates = []
                content = data.get("content", [])

                for rate_data in content:
                    try:
                        service = rate_data.get("service", {})
                        price = rate_data.get("price", {})

                        rate = ShippingRate(
                            courier_name=service.get("courier_name", "Unknown"),
                            courier_code=service.get("courier_code", ""),
                            service_code=service.get("flagship_code", ""),
                            service_name=service.get("courier_desc", "Standard"),
                            transit_days=rate_data.get("transit_time", 5),
                            estimated_delivery=rate_data.get("estimated_delivery_date"),
                            base_price=float(price.get("subtotal", 0)),
                            fuel_surcharge=float(
                                price.get("charges", {}).get("fuel_surcharge", 0)
                            ),
                            taxes=float(price.get("taxes", {}).get("gst", 0))
                            + float(price.get("taxes", {}).get("hst", 0))
                            + float(price.get("taxes", {}).get("pst", 0)),
                            total_price=float(price.get("total", 0)),
                            currency="CAD",
                        )
                        rates.append(rate)
                    except Exception as e:
                        print(f"Error processing rate: {e}")
                        continue

                # Sort by total price
                rates.sort(key=lambda x: x.total_price)
                return rates

        except httpx.HTTPStatusError as e:
            print(f"FlagShip API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Shipping rate error: {e.response.status_code}")
        except Exception as e:
            print(f"FlagShip connection error: {e}")
            raise Exception(f"Unable to get shipping rates: {str(e)}")

    async def create_shipment(
        self,
        to_address: ShippingAddress,
        packages: List[Package],
        selected_rate: ShippingRate,
        order_id: str,
    ) -> ShipmentResult:
        """
        Create a shipment and generate shipping label
        """
        await self._handle_rate_limit()

        payload = {
            "from": {
                "name": STORE_ORIGIN["name"],
                "attn": STORE_ORIGIN["attn"],
                "address": STORE_ORIGIN["address"],
                "suite": STORE_ORIGIN["suite"],
                "city": STORE_ORIGIN["city"],
                "state": STORE_ORIGIN["state"],
                "country": STORE_ORIGIN["country"],
                "postal_code": STORE_ORIGIN["postal_code"],
                "phone": STORE_ORIGIN["phone"],
                "is_commercial": STORE_ORIGIN["is_commercial"],
            },
            "to": {
                "name": to_address.name,
                "attn": to_address.name,  # Required by FlagShip API
                "address": to_address.address,
                "city": to_address.city,
                "state": to_address.state,
                "country": to_address.country,
                "postal_code": to_address.postal_code.replace(" ", "").upper(),
                "phone": to_address.phone or "",
                "is_commercial": to_address.is_commercial,
            },
            "packages": {
                "items": [
                    {
                        "weight": max(pkg.weight, 0.45),  # FlagShip minimum 0.45kg
                        "length": pkg.length,
                        "width": pkg.width,
                        "height": pkg.height,
                        "description": pkg.description,
                    }
                    for pkg in packages
                ],
                "units": "metric",
                "type": "package",
            },
            "payment": {"payer": "F"},
            "service": {
                "courier_name": selected_rate.courier_name,
                "courier_code": selected_rate.courier_code,
            },
            # FlagShip reference field max 30 chars - truncate order_id
            "options": {"signature_required": False, "reference": order_id[:30] if order_id else ""},
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                print(f"[FlagShip] Creating shipment with payload: from={STORE_ORIGIN['city']}, to={to_address.city}")
                
                # Create the shipment
                response = await client.post(
                    f"{self.base_url}/ship/confirm",
                    json=payload,
                    headers=self._get_headers(),
                )

                if response.status_code not in [200, 201]:
                    print(f"[FlagShip] Error response: {response.status_code} - {response.text}")
                    raise Exception(f"FlagShip API error: {response.text}")

                data = response.json()
                print(f"[FlagShip] Response: {data}")

                content = data.get("content", {})

                return ShipmentResult(
                    shipment_id=str(content.get("id", "")),
                    tracking_number=content.get("tracking_number", ""),
                    label_url=content.get("labels", {}).get("regular", ""),
                    thermal_label_url=content.get("labels", {}).get("thermal", ""),
                    courier_name=selected_rate.courier_name,
                    service_name=selected_rate.service_name,
                    total_cost=selected_rate.total_price,
                )

        except httpx.HTTPStatusError as e:
            error_text = e.response.text if hasattr(e, 'response') else str(e)
            print(f"[FlagShip] HTTP error: {e.response.status_code if hasattr(e, 'response') else 'unknown'} - {error_text}")
            raise Exception(f"Shipment creation failed: {error_text}")
        except Exception as e:
            print(f"[FlagShip] Shipment error: {e}")
            raise Exception(f"Unable to create shipment: {str(e)}")

    async def track_shipment(self, tracking_number: str) -> dict:
        """
        Get tracking information for a shipment
        """
        await self._handle_rate_limit()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/ship/track/{tracking_number}",
                    headers=self._get_headers(),
                )

                response.raise_for_status()
                return response.json()

        except Exception as e:
            print(f"Tracking error: {e}")
            return {"error": str(e), "status": "unknown"}

    async def void_shipment(self, shipment_id: str) -> bool:
        """
        Cancel/void a shipment
        """
        await self._handle_rate_limit()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/ship/shipments/{shipment_id}",
                    headers=self._get_headers(),
                )

                return response.status_code in [200, 204]

        except Exception as e:
            print(f"Void shipment error: {e}")
            return False

    async def list_shipments(self, limit: int = 50, page: int = 1) -> List[dict]:
        """
        List all shipments from FlagShip account
        
        Args:
            limit: Number of shipments per page (max 100)
            page: Page number
            
        Returns:
            List of shipment dictionaries
        """
        await self._handle_rate_limit()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/ship/shipments",
                    headers=self._get_headers(),
                    params={"limit": min(limit, 100), "page": page}
                )

                response.raise_for_status()
                data = response.json()
                
                # FlagShip returns {"content": [...shipments...], "total": N}
                shipments = data.get("content", []) if isinstance(data, dict) else data
                
                # Transform to simplified format
                result = []
                for s in shipments:
                    from_addr = s.get("from", {})
                    to_addr = s.get("to", {})
                    service = s.get("service", {})
                    
                    result.append({
                        "id": s.get("id"),
                        "tracking_number": s.get("tracking_number"),
                        "courier_name": service.get("courier_name", "Unknown"),
                        "courier_code": service.get("courier_code", ""),
                        "status": s.get("status", "unknown"),
                        "created_at": s.get("created_at"),
                        "shipped_at": s.get("shipped_at"),
                        "label_url": s.get("label", {}).get("pdf") if isinstance(s.get("label"), dict) else None,
                        "from": {
                            "name": from_addr.get("name", ""),
                            "attn": from_addr.get("attn", ""),
                            "address": from_addr.get("address", ""),
                            "city": from_addr.get("city", ""),
                            "state": from_addr.get("state", ""),
                            "postal_code": from_addr.get("postal_code", ""),
                            "country": from_addr.get("country", "CA"),
                        },
                        "to": {
                            "name": to_addr.get("name", ""),
                            "attn": to_addr.get("attn", ""),
                            "address": to_addr.get("address", ""),
                            "city": to_addr.get("city", ""),
                            "state": to_addr.get("state", ""),
                            "postal_code": to_addr.get("postal_code", ""),
                            "country": to_addr.get("country", "CA"),
                        },
                        "total_price": s.get("price", {}).get("total", 0) if isinstance(s.get("price"), dict) else 0,
                        "reference": s.get("options", {}).get("reference", "") if isinstance(s.get("options"), dict) else "",
                    })
                
                return result

        except Exception as e:
            print(f"[FlagShip] List shipments error: {e}")
            return []


# Global client instance
flagship_client = FlagShipClient()


# Helper functions for easy access
async def get_shipping_rates(to_address: dict, packages: List[dict]) -> List[dict]:
    """
    Get shipping rates - simplified interface for API routes

    Args:
        to_address: {name, address, city, state, postal_code, country, phone}
        packages: [{weight, length, width, height, description}]

    Returns:
        List of shipping rate options sorted by price
    """
    addr = ShippingAddress(**to_address)
    pkgs = [Package(**p) for p in packages]

    rates = await flagship_client.get_rates(addr, pkgs)
    return [rate.model_dump() for rate in rates]


async def create_shipping_label(
    to_address: dict, packages: List[dict], selected_rate: dict, order_id: str
) -> dict:
    """
    Create shipment and generate label - simplified interface

    Returns:
        {shipment_id, tracking_number, label_url, courier_name, total_cost}
    """
    addr = ShippingAddress(**to_address)
    pkgs = [Package(**p) for p in packages]
    rate = ShippingRate(**selected_rate)

    result = await flagship_client.create_shipment(addr, pkgs, rate, order_id)
    return result.model_dump()


async def auto_create_shipment(order: dict) -> Optional[dict]:
    """
    Automatically create a shipping label for an order.
    Uses the cheapest available shipping rate.
    
    Args:
        order: Order document from database with shipping_address
        
    Returns:
        Shipment result dict or None if failed
    """
    try:
        shipping_addr = order.get("shipping_address", {})
        order_id = order.get("id", "unknown")
        
        # Validate required shipping address fields
        required_fields = {
            'first_name': shipping_addr.get('first_name'),
            'address': shipping_addr.get('address_line1') or shipping_addr.get('address'),
            'city': shipping_addr.get('city'),
            'postal_code': shipping_addr.get('postal_code'),
            'province': shipping_addr.get('province') or shipping_addr.get('state')
        }
        
        missing = [field for field, value in required_fields.items() if not value]
        if missing:
            print(f"[AutoShip] Order {order_id}: Missing shipping address fields: {', '.join(missing)}")
            return None
        
        # Build destination address
        # Normalize country to 2-letter code
        raw_country = shipping_addr.get("country", "CA")
        country_code = raw_country.upper()[:2] if len(raw_country) == 2 else "CA"
        if raw_country.lower() in ["canada", "can"]:
            country_code = "CA"
        elif raw_country.lower() in ["united states", "usa", "us", "united states of america"]:
            country_code = "US"
        
        to_address = ShippingAddress(
            name=f"{shipping_addr.get('first_name', '')} {shipping_addr.get('last_name', '')}".strip(),
            address=shipping_addr.get("address_line1", "") or shipping_addr.get("address", ""),
            city=shipping_addr.get("city", ""),
            state=shipping_addr.get("province", "") or shipping_addr.get("state", ""),
            postal_code=shipping_addr.get("postal_code", ""),
            country=country_code,
            phone=shipping_addr.get("phone", ""),
            is_commercial=False
        )
        
        # Default package for skincare products
        # FlagShip minimum weight is 0.45 kg
        items = order.get("items", [])
        total_quantity = sum(item.get("quantity", 1) for item in items)
        
        # Calculate weight: ~300g per item, minimum 0.5kg for API compliance
        estimated_weight = 0.3 * total_quantity
        package_weight = max(0.5, estimated_weight)  # Minimum 0.5kg (FlagShip requires >= 0.45)
        
        packages = [Package(
            weight=package_weight,
            length=20,
            width=15,
            height=10 * max(1, total_quantity // 2),  # Stack if multiple items
            description="ReRoots Skincare Products"
        )]
        
        # Get available rates
        print(f"[AutoShip] Getting rates for order {order_id}")
        rates = await flagship_client.get_rates(to_address, packages)
        
        if not rates:
            print(f"[AutoShip] No shipping rates available for order {order.get('id')}")
            return None
        
        # Select the cheapest rate
        cheapest_rate = min(rates, key=lambda r: r.total_price)
        print(f"[AutoShip] Selected rate: {cheapest_rate.courier_name} - ${cheapest_rate.total_price}")
        
        # Create the shipment
        result = await flagship_client.create_shipment(
            to_address, 
            packages, 
            cheapest_rate, 
            order.get("id", "")
        )
        
        print(f"[AutoShip] Shipment created! Tracking: {result.tracking_number}")
        
        return {
            "shipment_id": result.shipment_id,
            "tracking_number": result.tracking_number,
            "label_url": result.label_url,
            "thermal_label_url": result.thermal_label_url,
            "courier_name": result.courier_name,
            "service_name": result.service_name,
            "total_cost": result.total_cost,
            "tracking_url": f"https://www.google.com/search?q={result.tracking_number}+tracking"
        }
        
    except Exception as e:
        print(f"[AutoShip] Error creating shipment: {e}")
        return None
