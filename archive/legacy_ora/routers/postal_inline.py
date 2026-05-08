"""
Canadian postal code geocoding & lookup
Extracted from server.py during modularization.
"""

import os
import logging
import json
import hashlib
import secrets
import time
import uuid
import re
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Query, Body, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
try:
    pass  # No models needed from server_models
except ImportError:
    pass
try:
    pass  # No email templates needed
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Common imports from server.py scope
import bcrypt
import jwt
try:
    import stripe
except ImportError:
    stripe = None

try:
    from performance_patch import limiter
except ImportError:
    limiter = type('obj', (object,), {'limit': lambda self, *a, **kw: lambda f: f})()

from middleware.security import sanitize_input, validate_email

try:
    from middleware.websocket_manager import WebSocketConnectionManager
    manager = WebSocketConnectionManager()
except ImportError:
    manager = None

from config import JWT_SECRET
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
SITE_URL = os.environ.get("SITE_URL", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# MongoDB client reference (set at startup)
client = None

def set_client(c):
    global client
    client = c


# Shared state — set by server.py at startup
db = None
api_router = None

def set_db(database):
    global db
    db = database

def set_router(router):
    global api_router
    api_router = router

def get_db():
    return db

router = APIRouter()

# ============ CANADIAN POSTAL CODE LOOKUP ============

# FSA (Forward Sortation Area) to City/Province mapping
# First character of postal code indicates province/region
# Second character indicates urban (1-9) or rural (0)
# Third character further narrows the location

# Province code from first letter of postal code
POSTAL_PROVINCE_MAP = {
    'A': 'NL',  # Newfoundland and Labrador
    'B': 'NS',  # Nova Scotia
    'C': 'PE',  # Prince Edward Island
    'E': 'NB',  # New Brunswick
    'G': 'QC',  # Quebec (East)
    'H': 'QC',  # Quebec (Montreal)
    'J': 'QC',  # Quebec (West)
    'K': 'ON',  # Ontario (East)
    'L': 'ON',  # Ontario (Central)
    'M': 'ON',  # Ontario (Toronto)
    'N': 'ON',  # Ontario (Southwest)
    'P': 'ON',  # Ontario (North)
    'R': 'MB',  # Manitoba
    'S': 'SK',  # Saskatchewan
    'T': 'AB',  # Alberta
    'V': 'BC',  # British Columbia
    'X': 'NT',  # Northwest Territories & Nunavut
    'Y': 'YT',  # Yukon
}

# Common FSA to City mappings (comprehensive list for major Canadian cities)
FSA_CITY_MAP = {
    # Ontario - Toronto (M)
    'M1B': 'Scarborough', 'M1C': 'Scarborough', 'M1E': 'Scarborough', 'M1G': 'Scarborough',
    'M1H': 'Scarborough', 'M1J': 'Scarborough', 'M1K': 'Scarborough', 'M1L': 'Scarborough',
    'M1M': 'Scarborough', 'M1N': 'Scarborough', 'M1P': 'Scarborough', 'M1R': 'Scarborough',
    'M1S': 'Scarborough', 'M1T': 'Scarborough', 'M1V': 'Scarborough', 'M1W': 'Scarborough',
    'M1X': 'Scarborough', 'M2H': 'North York', 'M2J': 'North York', 'M2K': 'North York',
    'M2L': 'North York', 'M2M': 'North York', 'M2N': 'North York', 'M2P': 'North York',
    'M2R': 'North York', 'M3A': 'North York', 'M3B': 'North York', 'M3C': 'North York',
    'M3H': 'North York', 'M3J': 'North York', 'M3K': 'North York', 'M3L': 'North York',
    'M3M': 'North York', 'M3N': 'North York', 'M4A': 'North York', 'M4B': 'East York',
    'M4C': 'East York', 'M4E': 'Toronto', 'M4G': 'Toronto', 'M4H': 'Toronto',
    'M4J': 'Toronto', 'M4K': 'Toronto', 'M4L': 'Toronto', 'M4M': 'Toronto',
    'M4N': 'Toronto', 'M4P': 'Toronto', 'M4R': 'Toronto', 'M4S': 'Toronto',
    'M4T': 'Toronto', 'M4V': 'Toronto', 'M4W': 'Toronto', 'M4X': 'Toronto',
    'M4Y': 'Toronto', 'M5A': 'Toronto', 'M5B': 'Toronto', 'M5C': 'Toronto',
    'M5E': 'Toronto', 'M5G': 'Toronto', 'M5H': 'Toronto', 'M5J': 'Toronto',
    'M5K': 'Toronto', 'M5L': 'Toronto', 'M5M': 'Toronto', 'M5N': 'Toronto',
    'M5P': 'Toronto', 'M5R': 'Toronto', 'M5S': 'Toronto', 'M5T': 'Toronto',
    'M5V': 'Toronto', 'M5W': 'Toronto', 'M5X': 'Toronto', 'M6A': 'North York',
    'M6B': 'North York', 'M6C': 'York', 'M6E': 'York', 'M6G': 'Toronto',
    'M6H': 'Toronto', 'M6J': 'Toronto', 'M6K': 'Toronto', 'M6L': 'North York',
    'M6M': 'York', 'M6N': 'York', 'M6P': 'Toronto', 'M6R': 'Toronto',
    'M6S': 'Toronto', 'M7A': 'Toronto', 'M7R': 'Mississauga', 'M7Y': 'Toronto',
    'M8V': 'Etobicoke', 'M8W': 'Etobicoke', 'M8X': 'Etobicoke', 'M8Y': 'Etobicoke',
    'M8Z': 'Etobicoke', 'M9A': 'Etobicoke', 'M9B': 'Etobicoke', 'M9C': 'Etobicoke',
    'M9L': 'North York', 'M9M': 'North York', 'M9N': 'York', 'M9P': 'Etobicoke',
    'M9R': 'Etobicoke', 'M9V': 'Etobicoke', 'M9W': 'Etobicoke',
    
    # Ontario - Ottawa (K)
    'K1A': 'Ottawa', 'K1B': 'Ottawa', 'K1C': 'Ottawa', 'K1E': 'Ottawa',
    'K1G': 'Ottawa', 'K1H': 'Ottawa', 'K1J': 'Ottawa', 'K1K': 'Ottawa',
    'K1L': 'Ottawa', 'K1M': 'Ottawa', 'K1N': 'Ottawa', 'K1P': 'Ottawa',
    'K1R': 'Ottawa', 'K1S': 'Ottawa', 'K1T': 'Ottawa', 'K1V': 'Ottawa',
    'K1W': 'Ottawa', 'K1X': 'Ottawa', 'K1Y': 'Ottawa', 'K1Z': 'Ottawa',
    'K2A': 'Ottawa', 'K2B': 'Ottawa', 'K2C': 'Ottawa', 'K2E': 'Ottawa',
    'K2G': 'Ottawa', 'K2H': 'Ottawa', 'K2J': 'Ottawa', 'K2K': 'Ottawa',
    'K2L': 'Ottawa', 'K2M': 'Ottawa', 'K2P': 'Ottawa', 'K2R': 'Ottawa',
    'K2S': 'Ottawa', 'K2T': 'Ottawa', 'K2V': 'Ottawa', 'K2W': 'Ottawa',
    'K4A': 'Ottawa', 'K4B': 'Ottawa', 'K4C': 'Ottawa', 'K4K': 'Rockland',
    'K4M': 'Manotick', 'K4P': 'Ottawa',
    
    # Ontario - Central (L)
    'L1A': 'Oshawa', 'L1B': 'Oshawa', 'L1C': 'Oshawa', 'L1G': 'Oshawa',
    'L1H': 'Oshawa', 'L1J': 'Oshawa', 'L1K': 'Oshawa', 'L1L': 'Oshawa',
    'L1M': 'Oshawa', 'L1N': 'Oshawa', 'L1P': 'Oshawa', 'L1R': 'Oshawa',
    'L1S': 'Oshawa', 'L1T': 'Whitby', 'L1V': 'Pickering', 'L1W': 'Pickering',
    'L1X': 'Pickering', 'L1Y': 'Pickering', 'L1Z': 'Ajax',
    'L3P': 'Markham', 'L3R': 'Markham', 'L3S': 'Markham', 'L3T': 'Thornhill',
    'L4B': 'Richmond Hill', 'L4C': 'Richmond Hill', 'L4E': 'Richmond Hill',
    'L4G': 'Aurora', 'L4H': 'Vaughan', 'L4J': 'Vaughan', 'L4K': 'Vaughan',
    'L4L': 'Vaughan', 'L5A': 'Mississauga', 'L5B': 'Mississauga',
    'L5C': 'Mississauga', 'L5E': 'Mississauga', 'L5G': 'Mississauga',
    'L5H': 'Mississauga', 'L5J': 'Mississauga', 'L5K': 'Mississauga',
    'L5L': 'Mississauga', 'L5M': 'Mississauga', 'L5N': 'Mississauga',
    'L5P': 'Mississauga', 'L5R': 'Mississauga', 'L5S': 'Mississauga',
    'L5T': 'Mississauga', 'L5V': 'Mississauga', 'L5W': 'Mississauga',
    'L6A': 'Maple', 'L6B': 'Maple', 'L6C': 'Maple', 'L6E': 'Markham',
    'L6G': 'Markham', 'L6H': 'Oakville', 'L6J': 'Oakville', 'L6K': 'Oakville',
    'L6L': 'Oakville', 'L6M': 'Oakville', 'L6P': 'Brampton', 'L6R': 'Brampton',
    'L6S': 'Brampton', 'L6T': 'Brampton', 'L6V': 'Brampton', 'L6W': 'Brampton',
    'L6X': 'Brampton', 'L6Y': 'Brampton', 'L6Z': 'Brampton',
    # L4T-L4Z area - Mississauga (near airport)
    'L4T': 'Mississauga', 'L4V': 'Mississauga', 'L4W': 'Mississauga',
    'L4X': 'Mississauga', 'L4Y': 'Mississauga', 'L4Z': 'Mississauga',
    'L7A': 'Brampton', 'L7C': 'Brampton', 'L7E': 'Bolton', 'L7G': 'Georgetown',
    'L7J': 'Acton', 'L7K': 'Caledon', 'L7L': 'Burlington', 'L7M': 'Burlington',
    'L7N': 'Burlington', 'L7P': 'Burlington', 'L7R': 'Burlington',
    'L7S': 'Burlington', 'L7T': 'Burlington', 'L8E': 'Hamilton',
    'L8G': 'Hamilton', 'L8H': 'Hamilton', 'L8J': 'Hamilton', 'L8K': 'Hamilton',
    'L8L': 'Hamilton', 'L8M': 'Hamilton', 'L8N': 'Hamilton', 'L8P': 'Hamilton',
    'L8R': 'Hamilton', 'L8S': 'Hamilton', 'L8T': 'Hamilton', 'L8V': 'Hamilton',
    'L8W': 'Hamilton', 'L9A': 'Hamilton', 'L9B': 'Hamilton', 'L9C': 'Hamilton',
    'L9G': 'Dundas', 'L9H': 'Dundas', 'L9K': 'Milton', 'L9T': 'Milton',
    
    # Ontario - Southwest (N)
    'N1C': 'Cambridge', 'N1E': 'Cambridge', 'N1G': 'Guelph', 'N1H': 'Guelph',
    'N1K': 'Guelph', 'N1L': 'Guelph', 'N1M': 'Guelph', 'N1P': 'Guelph',
    'N1R': 'Cambridge', 'N1S': 'Cambridge', 'N1T': 'Cambridge',
    'N2A': 'Kitchener', 'N2B': 'Kitchener', 'N2C': 'Kitchener',
    'N2E': 'Kitchener', 'N2G': 'Kitchener', 'N2H': 'Kitchener',
    'N2J': 'Waterloo', 'N2K': 'Waterloo', 'N2L': 'Waterloo',
    'N2M': 'Kitchener', 'N2N': 'Kitchener', 'N2P': 'Kitchener',
    'N2R': 'Kitchener', 'N2T': 'Waterloo', 'N2V': 'Waterloo',
    'N3A': 'Brantford', 'N3P': 'Brantford', 'N3R': 'Brantford',
    'N3S': 'Brantford', 'N3T': 'Brantford', 'N3V': 'Brantford',
    'N4B': 'Woodstock', 'N4G': 'Woodstock', 'N4S': 'Woodstock',
    'N4T': 'Woodstock', 'N4V': 'Woodstock', 'N5A': 'St. Thomas',
    'N5C': 'London', 'N5P': 'St. Thomas', 'N5R': 'St. Thomas',
    'N5V': 'London', 'N5W': 'London', 'N5X': 'London', 'N5Y': 'London',
    'N5Z': 'London', 'N6A': 'London', 'N6B': 'London', 'N6C': 'London',
    'N6E': 'London', 'N6G': 'London', 'N6H': 'London', 'N6J': 'London',
    'N6K': 'London', 'N6L': 'London', 'N6M': 'London', 'N6N': 'London',
    'N6P': 'London', 'N7A': 'Sarnia', 'N7G': 'Wallaceburg',
    'N7L': 'Sarnia', 'N7M': 'Sarnia', 'N7S': 'Sarnia', 'N7T': 'Sarnia',
    'N7V': 'Sarnia', 'N7W': 'Sarnia', 'N7X': 'Sarnia', 'N8A': 'Chatham',
    'N8H': 'Windsor', 'N8N': 'Windsor', 'N8P': 'Windsor', 'N8R': 'Windsor',
    'N8S': 'Windsor', 'N8T': 'Windsor', 'N8V': 'Windsor', 'N8W': 'Windsor',
    'N8X': 'Windsor', 'N8Y': 'Windsor', 'N9A': 'Windsor', 'N9B': 'Windsor',
    'N9C': 'Windsor', 'N9E': 'Windsor', 'N9G': 'Windsor', 'N9H': 'Windsor',
    'N9J': 'Windsor', 'N9K': 'Windsor', 'N9V': 'Windsor', 'N9Y': 'Windsor',
    
    # British Columbia (V)
    'V1A': 'Cranbrook', 'V1B': 'Cranbrook', 'V1C': 'Cranbrook',
    'V1E': 'Salmon Arm', 'V1G': 'Dawson Creek', 'V1H': 'Vernon',
    'V1J': 'Fort St. John', 'V1K': 'Kamloops', 'V1L': 'Nelson',
    'V1M': 'Langley', 'V1N': 'Castlegar', 'V1P': 'Kamloops',
    'V1R': 'Trail', 'V1S': 'Kamloops', 'V1T': 'Kamloops',
    'V1V': 'Kelowna', 'V1W': 'Kelowna', 'V1X': 'Kelowna',
    'V1Y': 'Kelowna', 'V1Z': 'Kelowna', 'V2A': 'Penticton',
    'V2B': 'Kamloops', 'V2C': 'Kamloops', 'V2E': 'Kamloops',
    'V2G': 'Williams Lake', 'V2H': 'Kamloops', 'V2J': 'Quesnel',
    'V2K': 'Prince George', 'V2L': 'Prince George', 'V2M': 'Prince George',
    'V2N': 'Prince George', 'V2P': 'Chilliwack', 'V2R': 'Chilliwack',
    'V2S': 'Abbotsford', 'V2T': 'Abbotsford', 'V2V': 'Mission',
    'V2W': 'Abbotsford', 'V2X': 'Abbotsford', 'V2Y': 'Abbotsford',
    'V2Z': 'Aldergrove', 'V3A': 'New Westminster', 'V3B': 'Port Coquitlam',
    'V3C': 'Port Coquitlam', 'V3E': 'Port Coquitlam', 'V3G': 'Hope',
    'V3H': 'Port Moody', 'V3J': 'Coquitlam', 'V3K': 'Coquitlam',
    'V3L': 'New Westminster', 'V3M': 'New Westminster', 'V3N': 'Burnaby',
    'V3R': 'Surrey', 'V3S': 'Surrey', 'V3T': 'Surrey', 'V3V': 'Surrey',
    'V3W': 'Surrey', 'V3X': 'Surrey', 'V3Y': 'Langley', 'V3Z': 'Langley',
    'V4A': 'Surrey', 'V4B': 'White Rock', 'V4C': 'Delta', 'V4E': 'Delta',
    'V4G': 'Delta', 'V4K': 'Delta', 'V4L': 'Delta', 'V4M': 'Delta',
    'V4N': 'Surrey', 'V4P': 'Surrey', 'V4R': 'Langley', 'V4W': 'Langley',
    'V5A': 'Burnaby', 'V5B': 'Burnaby', 'V5C': 'Burnaby', 'V5E': 'Burnaby',
    'V5G': 'Burnaby', 'V5H': 'Burnaby', 'V5J': 'Burnaby', 'V5K': 'Vancouver',
    'V5L': 'Vancouver', 'V5M': 'Vancouver', 'V5N': 'Vancouver',
    'V5P': 'Vancouver', 'V5R': 'Vancouver', 'V5S': 'Vancouver',
    'V5T': 'Vancouver', 'V5V': 'Vancouver', 'V5W': 'Vancouver',
    'V5X': 'Vancouver', 'V5Y': 'Vancouver', 'V5Z': 'Vancouver',
    'V6A': 'Vancouver', 'V6B': 'Vancouver', 'V6C': 'Vancouver',
    'V6E': 'Vancouver', 'V6G': 'Vancouver', 'V6H': 'Vancouver',
    'V6J': 'Vancouver', 'V6K': 'Vancouver', 'V6L': 'Vancouver',
    'V6M': 'Vancouver', 'V6N': 'Vancouver', 'V6P': 'Vancouver',
    'V6R': 'Vancouver', 'V6S': 'Vancouver', 'V6T': 'Vancouver',
    'V6V': 'Richmond', 'V6W': 'Richmond', 'V6X': 'Richmond',
    'V6Y': 'Richmond', 'V6Z': 'Vancouver', 'V7A': 'Richmond',
    'V7B': 'Richmond', 'V7C': 'Richmond', 'V7E': 'Richmond',
    'V7G': 'North Vancouver', 'V7H': 'North Vancouver', 'V7J': 'North Vancouver',
    'V7K': 'North Vancouver', 'V7L': 'North Vancouver', 'V7M': 'North Vancouver',
    'V7N': 'North Vancouver', 'V7P': 'North Vancouver', 'V7R': 'North Vancouver',
    'V7S': 'West Vancouver', 'V7T': 'West Vancouver', 'V7V': 'West Vancouver',
    'V7W': 'West Vancouver', 'V7X': 'Vancouver', 'V7Y': 'Vancouver',
    'V8A': 'Powell River', 'V8B': 'Squamish', 'V8C': 'Kitimat',
    'V8G': 'Terrace', 'V8J': 'Prince Rupert', 'V8K': 'Saltspring Island',
    'V8L': 'Sidney', 'V8M': 'Sidney', 'V8N': 'Victoria', 'V8P': 'Victoria',
    'V8R': 'Victoria', 'V8S': 'Victoria', 'V8T': 'Victoria', 'V8V': 'Victoria',
    'V8W': 'Victoria', 'V8X': 'Saanich', 'V8Y': 'Victoria', 'V8Z': 'Saanich',
    'V9A': 'Victoria', 'V9B': 'Victoria', 'V9C': 'Victoria', 'V9E': 'Victoria',
    'V9G': 'Ladysmith', 'V9J': 'Parksville', 'V9K': 'Qualicum Beach',
    'V9L': 'Duncan', 'V9M': 'Duncan', 'V9N': 'Courtenay', 'V9P': 'Parksville',
    'V9R': 'Nanaimo', 'V9S': 'Nanaimo', 'V9T': 'Nanaimo', 'V9V': 'Nanaimo',
    'V9W': 'Campbell River', 'V9X': 'Campbell River', 'V9Y': 'Port Alberni',
    
    # Alberta (T)
    'T1A': 'Medicine Hat', 'T1B': 'Medicine Hat', 'T1C': 'Medicine Hat',
    'T1G': 'Lethbridge', 'T1H': 'Lethbridge', 'T1J': 'Lethbridge',
    'T1K': 'Lethbridge', 'T1L': 'Banff', 'T1M': 'Brooks',
    'T1P': 'Strathmore', 'T1R': 'Taber', 'T1S': 'Okotoks',
    'T1V': 'High River', 'T1W': 'Canmore', 'T1X': 'Chestermere',
    'T1Y': 'Calgary', 'T2A': 'Calgary', 'T2B': 'Calgary', 'T2C': 'Calgary',
    'T2E': 'Calgary', 'T2G': 'Calgary', 'T2H': 'Calgary', 'T2J': 'Calgary',
    'T2K': 'Calgary', 'T2L': 'Calgary', 'T2M': 'Calgary', 'T2N': 'Calgary',
    'T2P': 'Calgary', 'T2R': 'Calgary', 'T2S': 'Calgary', 'T2T': 'Calgary',
    'T2V': 'Calgary', 'T2W': 'Calgary', 'T2X': 'Calgary', 'T2Y': 'Calgary',
    'T2Z': 'Calgary', 'T3A': 'Calgary', 'T3B': 'Calgary', 'T3C': 'Calgary',
    'T3E': 'Calgary', 'T3G': 'Calgary', 'T3H': 'Calgary', 'T3J': 'Calgary',
    'T3K': 'Calgary', 'T3L': 'Calgary', 'T3M': 'Calgary', 'T3N': 'Calgary',
    'T3P': 'Calgary', 'T3R': 'Calgary', 'T3S': 'De Winton', 'T3Z': 'Bragg Creek',
    'T4A': 'Cochrane', 'T4B': 'Cochrane', 'T4C': 'Cochrane',
    'T4E': 'Ponoka', 'T4G': 'Wetaskiwin', 'T4H': 'Red Deer',
    'T4J': 'Lacombe', 'T4L': 'Red Deer', 'T4N': 'Red Deer',
    'T4P': 'Red Deer', 'T4R': 'Red Deer', 'T4S': 'Sylvan Lake',
    'T4T': 'Rocky Mountain House', 'T4V': 'Camrose',
    'T5A': 'Edmonton', 'T5B': 'Edmonton', 'T5C': 'Edmonton',
    'T5E': 'Edmonton', 'T5G': 'Edmonton', 'T5H': 'Edmonton',
    'T5J': 'Edmonton', 'T5K': 'Edmonton', 'T5L': 'Edmonton',
    'T5M': 'Edmonton', 'T5N': 'Edmonton', 'T5P': 'Edmonton',
    'T5R': 'Edmonton', 'T5S': 'Edmonton', 'T5T': 'Edmonton',
    'T5V': 'Edmonton', 'T5W': 'Edmonton', 'T5X': 'Edmonton',
    'T5Y': 'Edmonton', 'T5Z': 'Edmonton', 'T6A': 'Edmonton',
    'T6B': 'Edmonton', 'T6C': 'Edmonton', 'T6E': 'Edmonton',
    'T6G': 'Edmonton', 'T6H': 'Edmonton', 'T6J': 'Edmonton',
    'T6K': 'Edmonton', 'T6L': 'Edmonton', 'T6M': 'Edmonton',
    'T6N': 'Edmonton', 'T6P': 'Edmonton', 'T6R': 'Edmonton',
    'T6S': 'Edmonton', 'T6T': 'Edmonton', 'T6V': 'Edmonton',
    'T6W': 'Edmonton', 'T6X': 'Edmonton', 'T7A': 'Spruce Grove',
    'T7E': 'Edson', 'T7N': 'Drayton Valley', 'T7P': 'Whitecourt',
    'T7S': 'Spruce Grove', 'T7X': 'Stony Plain', 'T7Y': 'Spruce Grove',
    'T7Z': 'Spruce Grove', 'T8A': 'Sherwood Park', 'T8B': 'Sherwood Park',
    'T8C': 'Sherwood Park', 'T8E': 'Sherwood Park', 'T8G': 'Sherwood Park',
    'T8H': 'Sherwood Park', 'T8L': 'Fort Saskatchewan',
    'T8N': 'St. Albert', 'T8R': 'St. Albert', 'T8T': 'St. Albert',
    'T8V': 'Leduc', 'T8W': 'Devon', 'T8X': 'Beaumont',
    'T9A': 'Grande Prairie', 'T9C': 'Grande Prairie', 'T9E': 'Nisku',
    'T9G': 'Morinville', 'T9H': 'Fort McMurray', 'T9J': 'Fort McMurray',
    'T9K': 'Fort McMurray', 'T9M': 'Lac La Biche', 'T9S': 'Lloydminster',
    'T9V': 'Cold Lake', 'T9W': 'Bonnyville', 'T9X': 'Vegreville',
    
    # Quebec - Montreal (H)
    'H1A': 'Montreal', 'H1B': 'Montreal', 'H1C': 'Montreal',
    'H1E': 'Montreal', 'H1G': 'Montreal', 'H1H': 'Montreal',
    'H1J': 'Montreal', 'H1K': 'Montreal', 'H1L': 'Montreal',
    'H1M': 'Montreal', 'H1N': 'Montreal', 'H1P': 'Montreal',
    'H1R': 'Montreal', 'H1S': 'Montreal', 'H1T': 'Montreal',
    'H1V': 'Montreal', 'H1W': 'Montreal', 'H1X': 'Montreal',
    'H1Y': 'Montreal', 'H1Z': 'Montreal', 'H2A': 'Montreal',
    'H2B': 'Montreal', 'H2C': 'Montreal', 'H2E': 'Montreal',
    'H2G': 'Montreal', 'H2H': 'Montreal', 'H2J': 'Montreal',
    'H2K': 'Montreal', 'H2L': 'Montreal', 'H2M': 'Montreal',
    'H2N': 'Montreal', 'H2P': 'Montreal', 'H2R': 'Montreal',
    'H2S': 'Montreal', 'H2T': 'Montreal', 'H2V': 'Montreal',
    'H2W': 'Montreal', 'H2X': 'Montreal', 'H2Y': 'Montreal',
    'H2Z': 'Montreal', 'H3A': 'Montreal', 'H3B': 'Montreal',
    'H3C': 'Montreal', 'H3E': 'Verdun', 'H3G': 'Montreal',
    'H3H': 'Montreal', 'H3J': 'Montreal', 'H3K': 'Montreal',
    'H3L': 'Montreal', 'H3M': 'Montreal', 'H3N': 'Montreal',
    'H3P': 'Montreal', 'H3R': 'Montreal', 'H3S': 'Montreal',
    'H3T': 'Montreal', 'H3V': 'Montreal', 'H3W': 'Montreal',
    'H3X': 'Montreal', 'H3Y': 'Westmount', 'H3Z': 'Westmount',
    'H4A': 'Montreal', 'H4B': 'Montreal', 'H4C': 'Montreal',
    'H4E': 'Verdun', 'H4G': 'Verdun', 'H4H': 'Verdun',
    'H4J': 'Montreal', 'H4K': 'Montreal', 'H4L': 'Saint-Laurent',
    'H4M': 'Saint-Laurent', 'H4N': 'Saint-Laurent', 'H4P': 'Saint-Laurent',
    'H4R': 'Saint-Laurent', 'H4S': 'Saint-Laurent', 'H4T': 'Saint-Laurent',
    'H4V': 'Verdun', 'H4W': 'Cote Saint-Luc', 'H4X': 'Montreal',
    'H4Y': 'Dorval', 'H4Z': 'Montreal', 'H5A': 'Montreal',
    'H5B': 'Montreal', 'H7A': 'Laval', 'H7B': 'Laval',
    'H7C': 'Laval', 'H7E': 'Laval', 'H7G': 'Laval', 'H7H': 'Laval',
    'H7J': 'Laval', 'H7K': 'Laval', 'H7L': 'Laval', 'H7M': 'Laval',
    'H7N': 'Laval', 'H7P': 'Laval', 'H7R': 'Laval', 'H7S': 'Laval',
    'H7T': 'Laval', 'H7V': 'Laval', 'H7W': 'Laval', 'H7X': 'Laval',
    'H7Y': 'Laval', 'H8N': 'LaSalle', 'H8P': 'LaSalle',
    'H8R': 'LaSalle', 'H8S': 'LaSalle', 'H8T': 'LaSalle',
    'H8Y': 'Pointe-Claire', 'H8Z': 'Pointe-Claire',
    'H9A': 'Pointe-Claire', 'H9B': 'Pointe-Claire',
    'H9C': 'Pointe-Claire', 'H9E': 'Kirkland', 'H9G': 'Kirkland',
    'H9H': 'Pierrefonds', 'H9J': 'Pierrefonds', 'H9K': 'Pierrefonds',
    'H9P': 'Dorval', 'H9R': 'Dorval', 'H9S': 'Dorval',
    'H9W': 'Sainte-Anne-de-Bellevue', 'H9X': 'Beaconsfield',
    
    # Quebec - Other (G, J)
    'G1A': 'Quebec City', 'G1B': 'Quebec City', 'G1C': 'Quebec City',
    'G1E': 'Quebec City', 'G1G': 'Quebec City', 'G1H': 'Quebec City',
    'G1J': 'Quebec City', 'G1K': 'Quebec City', 'G1L': 'Quebec City',
    'G1M': 'Quebec City', 'G1N': 'Quebec City', 'G1P': 'Quebec City',
    'G1R': 'Quebec City', 'G1S': 'Quebec City', 'G1T': 'Quebec City',
    'G1V': 'Quebec City', 'G1W': 'Quebec City', 'G1X': 'Quebec City',
    'G1Y': 'Quebec City', 'G2A': 'Quebec City', 'G2B': 'Quebec City',
    'G2C': 'Quebec City', 'G2E': 'Quebec City', 'G2G': 'Quebec City',
    'G2J': 'Quebec City', 'G2K': 'Quebec City', 'G2L': 'Quebec City',
    'G2M': 'Quebec City', 'G2N': 'Quebec City', 'G3A': 'Cap-Rouge',
    'G3B': 'Lac-Beauport', 'G3C': 'Cap-Rouge', 'G3E': 'Sainte-Foy',
    'G3G': 'Ancienne-Lorette', 'G3H': 'Saint-Augustin',
    'G3J': 'Sainte-Catherine', 'G3K': 'Shannon',
    'J1C': 'Saint-Hyacinthe', 'J1E': 'Granby', 'J1G': 'Drummondville',
    'J1H': 'Sherbrooke', 'J1J': 'Sherbrooke', 'J1K': 'Sherbrooke',
    'J1L': 'Sherbrooke', 'J1M': 'Sherbrooke', 'J1N': 'Sherbrooke',
    'J1R': 'Sherbrooke', 'J1S': 'Sherbrooke', 'J2A': 'Saint-Jean-sur-Richelieu',
    'J2B': 'Saint-Jean-sur-Richelieu', 'J2G': 'Victoriaville',
    'J2H': 'Victoriaville', 'J2S': 'Saint-Hyacinthe',
    'J2T': 'Saint-Hyacinthe', 'J2W': 'Salaberry-de-Valleyfield',
    'J2X': 'Salaberry-de-Valleyfield', 'J3B': 'Chambly',
    'J3E': 'Sainte-Julie', 'J3G': 'Candiac', 'J3H': 'Saint-Basile-le-Grand',
    'J3L': 'Chambly', 'J3M': 'Carignan', 'J3N': 'Boucherville',
    'J3V': 'Longueuil', 'J3X': 'Longueuil', 'J3Y': 'Longueuil',
    'J3Z': 'Longueuil', 'J4B': 'Longueuil', 'J4G': 'Longueuil',
    'J4H': 'Longueuil', 'J4J': 'Longueuil', 'J4K': 'Longueuil',
    'J4L': 'Longueuil', 'J4M': 'Longueuil', 'J4N': 'Longueuil',
    'J4P': 'Longueuil', 'J4R': 'Longueuil', 'J4S': 'Longueuil',
    'J4T': 'Longueuil', 'J4V': 'Brossard', 'J4W': 'Brossard',
    'J4X': 'Brossard', 'J4Y': 'Brossard', 'J4Z': 'Brossard',
    'J5A': 'Varennes', 'J5B': 'Saint-Amable', 'J5C': 'Sainte-Julie',
    'J5J': 'Terrebonne', 'J5L': 'Repentigny', 'J5M': 'Rosemere',
    'J5R': 'Blainville', 'J5T': 'Blainville', 'J5W': 'Mascouche',
    'J5X': 'Terrebonne', 'J5Y': 'Terrebonne', 'J5Z': 'Terrebonne',
    'J6A': 'Repentigny', 'J6E': 'Joliette', 'J6J': 'Sainte-Therese',
    'J6K': 'Sainte-Therese', 'J6N': 'Blainville', 'J6R': 'Boisbriand',
    'J6S': 'Boisbriand', 'J6T': 'Boisbriand', 'J6V': 'Lorraine',
    'J6W': 'Lorraine', 'J6X': 'Saint-Eustache', 'J6Y': 'Saint-Eustache',
    'J6Z': 'Saint-Eustache', 'J7A': 'Saint-Eustache', 'J7B': 'Deux-Montagnes',
    'J7C': 'Oka', 'J7E': 'Sainte-Marthe-sur-le-Lac', 'J7G': 'Mirabel',
    'J7H': 'Lachute', 'J7J': 'Mirabel', 'J7K': 'Mirabel',
    'J7L': 'Mirabel', 'J7M': 'Mirabel', 'J7N': 'Mirabel',
    'J7P': 'Saint-Jerome', 'J7R': 'Saint-Jerome', 'J7T': 'Mont-Tremblant',
    'J7V': 'Vaudreuil-Dorion', 'J7W': 'Vaudreuil-Dorion',
    'J7X': 'Vaudreuil-Dorion', 'J7Y': 'Vaudreuil-Dorion',
    'J7Z': 'Saint-Jerome', 'J8A': 'Saint-Jerome', 'J8B': 'Prevost',
    'J8E': 'Sainte-Agathe-des-Monts', 'J8G': 'Mont-Tremblant',
    'J8H': 'Lachute', 'J8L': 'Buckingham', 'J8M': 'Gatineau',
    'J8N': 'Gatineau', 'J8P': 'Gatineau', 'J8R': 'Gatineau',
    'J8T': 'Gatineau', 'J8V': 'Gatineau', 'J8X': 'Gatineau',
    'J8Y': 'Gatineau', 'J8Z': 'Gatineau', 'J9A': 'Gatineau',
    'J9B': 'Chelsea', 'J9E': 'Cantley', 'J9H': 'Gatineau',
    'J9J': 'Gatineau', 'J9P': 'Mont-Laurier', 'J9T': 'Rouyn-Noranda',
    'J9V': 'La Sarre', 'J9X': 'Val-d\'Or', 'J9Y': 'Val-d\'Or',
    'J9Z': 'Amos',
    
    # Manitoba (R)
    'R2C': 'Winnipeg', 'R2E': 'Winnipeg', 'R2G': 'Winnipeg',
    'R2H': 'Winnipeg', 'R2J': 'Winnipeg', 'R2K': 'Winnipeg',
    'R2L': 'Winnipeg', 'R2M': 'Winnipeg', 'R2N': 'Winnipeg',
    'R2P': 'Winnipeg', 'R2R': 'Winnipeg', 'R2V': 'Winnipeg',
    'R2W': 'Winnipeg', 'R2X': 'Winnipeg', 'R2Y': 'Winnipeg',
    'R3A': 'Winnipeg', 'R3B': 'Winnipeg', 'R3C': 'Winnipeg',
    'R3E': 'Winnipeg', 'R3G': 'Winnipeg', 'R3H': 'Winnipeg',
    'R3J': 'Winnipeg', 'R3K': 'Winnipeg', 'R3L': 'Winnipeg',
    'R3M': 'Winnipeg', 'R3N': 'Winnipeg', 'R3P': 'Winnipeg',
    'R3R': 'Winnipeg', 'R3S': 'Winnipeg', 'R3T': 'Winnipeg',
    'R3V': 'Winnipeg', 'R3W': 'Winnipeg', 'R3X': 'Winnipeg',
    'R3Y': 'Winnipeg', 'R4A': 'Winnipeg', 'R4G': 'St. Andrews',
    'R4H': 'St. Andrews', 'R4J': 'Oakbank', 'R4K': 'Oakbank',
    'R4L': 'Lorette', 'R5A': 'Selkirk', 'R5G': 'Selkirk',
    'R5H': 'Stonewall', 'R6M': 'Steinbach', 'R6W': 'Steinbach',
    'R7A': 'Brandon', 'R7B': 'Brandon', 'R7C': 'Brandon',
    'R8A': 'Flin Flon', 'R8N': 'Thompson',
    
    # Saskatchewan (S)
    'S4H': 'Regina', 'S4K': 'Regina', 'S4L': 'Regina', 'S4M': 'Regina',
    'S4N': 'Regina', 'S4P': 'Regina', 'S4R': 'Regina', 'S4S': 'Regina',
    'S4T': 'Regina', 'S4V': 'Regina', 'S4W': 'Regina', 'S4X': 'Regina',
    'S4Y': 'Regina', 'S4Z': 'Regina', 'S6H': 'Moose Jaw', 'S6J': 'Moose Jaw',
    'S6K': 'Moose Jaw', 'S6V': 'Prince Albert', 'S6W': 'Prince Albert',
    'S6X': 'Prince Albert', 'S7H': 'Saskatoon', 'S7J': 'Saskatoon',
    'S7K': 'Saskatoon', 'S7L': 'Saskatoon', 'S7M': 'Saskatoon',
    'S7N': 'Saskatoon', 'S7P': 'Saskatoon', 'S7R': 'Saskatoon',
    'S7S': 'Saskatoon', 'S7T': 'Saskatoon', 'S7V': 'Saskatoon',
    'S7W': 'Saskatoon', 'S9A': 'North Battleford', 'S9H': 'Swift Current',
    'S9V': 'Yorkton',
    
    # Nova Scotia (B)
    'B1A': 'Glace Bay', 'B1B': 'Glace Bay', 'B1C': 'Sydney Mines',
    'B1E': 'Sydney', 'B1G': 'Sydney', 'B1H': 'Sydney', 'B1J': 'Sydney',
    'B1K': 'Sydney', 'B1L': 'Sydney', 'B1M': 'Sydney', 'B1N': 'Sydney',
    'B1P': 'Sydney', 'B1R': 'Sydney', 'B1S': 'Sydney', 'B1V': 'Sydney',
    'B1Y': 'North Sydney', 'B2A': 'North Sydney', 'B2C': 'Sydney',
    'B2E': 'Sydney', 'B2G': 'Baddeck', 'B2H': 'St. Peter\'s',
    'B2N': 'Truro', 'B2R': 'Halifax', 'B2S': 'Halifax',
    'B2T': 'Halifax', 'B2V': 'Halifax', 'B2W': 'Halifax',
    'B2X': 'Dartmouth', 'B2Y': 'Dartmouth', 'B2Z': 'Halifax',
    'B3A': 'Dartmouth', 'B3B': 'Dartmouth', 'B3E': 'Halifax',
    'B3G': 'Halifax', 'B3H': 'Halifax', 'B3J': 'Halifax',
    'B3K': 'Halifax', 'B3L': 'Halifax', 'B3M': 'Halifax',
    'B3N': 'Halifax', 'B3P': 'Halifax', 'B3R': 'Halifax',
    'B3S': 'Halifax', 'B3T': 'Halifax', 'B3V': 'Halifax',
    'B3Z': 'Halifax', 'B4A': 'Dartmouth', 'B4B': 'Dartmouth',
    'B4C': 'Dartmouth', 'B4E': 'Dartmouth', 'B4G': 'Lawrencetown',
    'B4H': 'Enfield', 'B4N': 'Kentville', 'B4P': 'Wolfville',
    'B4R': 'Greenwood', 'B4V': 'Bridgewater', 'B5A': 'Yarmouth',
    
    # New Brunswick (E)
    'E1A': 'Moncton', 'E1B': 'Moncton', 'E1C': 'Moncton',
    'E1E': 'Moncton', 'E1G': 'Moncton', 'E1H': 'Moncton',
    'E1J': 'Dieppe', 'E1N': 'Riverview', 'E1V': 'Bathurst',
    'E1W': 'Bathurst', 'E2A': 'Miramichi', 'E2E': 'Saint John',
    'E2G': 'Saint John', 'E2H': 'Saint John', 'E2J': 'Saint John',
    'E2K': 'Saint John', 'E2L': 'Saint John', 'E2M': 'Saint John',
    'E2N': 'Saint John', 'E2P': 'Saint John', 'E2R': 'Saint John',
    'E2S': 'Saint John', 'E3A': 'Fredericton', 'E3B': 'Fredericton',
    'E3C': 'Fredericton', 'E3E': 'Fredericton', 'E3G': 'Fredericton',
    'E3L': 'St. Stephen', 'E3N': 'Woodstock', 'E3V': 'Edmundston',
    'E3Y': 'Grand Falls', 'E3Z': 'Grand Falls', 'E4E': 'Shediac',
    'E4G': 'Sackville', 'E4K': 'Sussex', 'E4L': 'Oromocto',
    'E4M': 'Quispamsis', 'E4N': 'Rothesay', 'E4P': 'Riverview',
    'E4R': 'Dieppe', 'E4T': 'Dieppe', 'E4W': 'Moncton',
    'E4X': 'Moncton', 'E4Y': 'Moncton', 'E4Z': 'Moncton',
    
    # Newfoundland and Labrador (A)
    'A1A': 'St. John\'s', 'A1B': 'St. John\'s', 'A1C': 'St. John\'s',
    'A1E': 'St. John\'s', 'A1G': 'St. John\'s', 'A1H': 'St. John\'s',
    'A1K': 'Paradise', 'A1L': 'Mount Pearl', 'A1M': 'Mount Pearl',
    'A1N': 'Mount Pearl', 'A1S': 'St. John\'s', 'A1V': 'St. John\'s',
    'A1W': 'St. John\'s', 'A1X': 'St. John\'s', 'A1Y': 'St. John\'s',
    'A2A': 'Corner Brook', 'A2B': 'Corner Brook', 'A2H': 'Corner Brook',
    'A2N': 'Grand Falls-Windsor', 'A2V': 'Gander',
    
    # Prince Edward Island (C)
    'C1A': 'Charlottetown', 'C1B': 'Charlottetown', 'C1C': 'Charlottetown',
    'C1E': 'Charlottetown', 'C1N': 'Summerside',
    
    # Northwest Territories/Nunavut (X)
    'X0A': 'Iqaluit', 'X0B': 'Rankin Inlet', 'X0C': 'Cambridge Bay',
    'X0E': 'Hay River', 'X0G': 'Yellowknife', 'X1A': 'Yellowknife',
    
    # Yukon (Y)
    'Y1A': 'Whitehorse',
}


class PostalCodeLookupResponse(BaseModel):
    fsa: str
    city: Optional[str] = None
    province: Optional[str] = None
    province_name: Optional[str] = None
    found: bool = False


@router.get("/postal-code/lookup")
async def postal_code_lookup(postal_code: str):
    """
    Look up city and province from a Canadian postal code.
    Uses the first 3 characters (FSA - Forward Sortation Area).
    """
    # Clean and validate postal code
    postal_code = postal_code.upper().replace(" ", "").strip()
    
    if len(postal_code) < 3:
        return PostalCodeLookupResponse(
            fsa=postal_code,
            found=False
        )
    
    fsa = postal_code[:3].upper()
    first_letter = fsa[0]
    
    # Get province from first letter
    province_code = POSTAL_PROVINCE_MAP.get(first_letter)
    
    if not province_code:
        return PostalCodeLookupResponse(
            fsa=fsa,
            found=False
        )
    
    # Province full names
    province_names = {
        'AB': 'Alberta', 'BC': 'British Columbia', 'MB': 'Manitoba',
        'NB': 'New Brunswick', 'NL': 'Newfoundland and Labrador',
        'NS': 'Nova Scotia', 'NT': 'Northwest Territories',
        'NU': 'Nunavut', 'ON': 'Ontario', 'PE': 'Prince Edward Island',
        'QC': 'Quebec', 'SK': 'Saskatchewan', 'YT': 'Yukon'
    }
    
    # Look up city from FSA
    city = FSA_CITY_MAP.get(fsa)
    
    return PostalCodeLookupResponse(
        fsa=fsa,
        city=city,
        province=province_code,
        province_name=province_names.get(province_code),
        found=True
    )


