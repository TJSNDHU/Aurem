"""
Customer Memory Extraction Service
═══════════════════════════════════════════════════════════════════
Extracts customer preferences and history from chat conversations.
Stores profiles in MongoDB for personalized future interactions.

CROSS-DEVICE MEMORY:
When a user logs in, their session-based profile is merged with their
account-based profile (keyed by email). This allows conversation memory
to persist across devices and browsers.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import re
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# Import TOON converter
from utils.toon import json_to_toon

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# CUSTOMER PROFILE SCHEMA
# ═══════════════════════════════════════════════════════════════════

EMPTY_PROFILE = {
    "skin_type": None,           # dry, oily, combination, sensitive, normal
    "skin_concerns": [],         # acne, wrinkles, dark spots, redness, etc.
    "products_mentioned": [],    # Products customer asked about
    "products_interested": [],   # Products showing purchase intent
    "allergies": [],             # Ingredients to avoid
    "age_range": None,           # teen, 20s, 30s, 40s, 50+
    "purchase_intent": "none",   # none, browsing, considering, ready
    "preferences": {},           # fragrance-free, vegan, etc.
    "last_topics": [],           # Recent conversation topics
    "interaction_count": 0,
    "first_seen": None,
    "last_seen": None,
}

# ═══════════════════════════════════════════════════════════════════
# EXTRACTION PATTERNS
# ═══════════════════════════════════════════════════════════════════

SKIN_TYPE_PATTERNS = {
    "dry": [r"\bdry\s+skin\b", r"\bmy skin is dry\b", r"\bdryness\b", r"\bflaky\b", r"\btight skin\b"],
    "oily": [r"\boily\s+skin\b", r"\bmy skin is oily\b", r"\bgreasy\b", r"\bshiny skin\b", r"\bexcess oil\b"],
    "combination": [r"\bcombination\s+skin\b", r"\bt-zone\b", r"\boily and dry\b"],
    "sensitive": [r"\bsensitive\s+skin\b", r"\beasily irritated\b", r"\breactive skin\b", r"\bredness\b"],
    "normal": [r"\bnormal\s+skin\b", r"\bbalanced skin\b"],
}

SKIN_CONCERNS = {
    "acne": [r"\bacne\b", r"\bpimples?\b", r"\bbreakouts?\b", r"\bblemish\b", r"\bzits?\b"],
    "wrinkles": [r"\bwrinkles?\b", r"\bfine lines?\b", r"\baging\b", r"\banti-aging\b", r"\bage recovery\b"],
    "dark_spots": [r"\bdark spots?\b", r"\bhyperpigmentation\b", r"\bmelasma\b", r"\bsun spots?\b", r"\buneven tone\b"],
    "redness": [r"\bredness\b", r"\brosacea\b", r"\bflushing\b", r"\birritati\b"],
    "dullness": [r"\bdull\b", r"\blackluster\b", r"\btired skin\b", r"\bno glow\b"],
    "dehydration": [r"\bdehydrat\b", r"\black of moisture\b", r"\bparched\b"],
    "large_pores": [r"\blarge pores?\b", r"\bvisible pores?\b", r"\bpore size\b"],
    "dark_circles": [r"\bdark circles?\b", r"\bunder eye\b", r"\beye bags?\b", r"\bpuffy eyes?\b"],
}

ALLERGY_PATTERNS = [
    r"(?:i'?m |i am )?allergic to (\w+(?:\s+\w+)?)",
    r"(\w+(?:\s+\w+)?) (?:causes?|gives? me) (?:a )?reaction",
    r"avoid (\w+(?:\s+\w+)?)",
    r"sensitive to (\w+(?:\s+\w+)?)",
    r"can'?t use (\w+(?:\s+\w+)?)",
]

PURCHASE_INTENT_SIGNALS = {
    "ready": [
        r"\bwant to buy\b", r"\bready to order\b", r"\bhow do i purchase\b",
        r"\badd to cart\b", r"\bcheckout\b", r"\bplace.+order\b", r"\bbuy now\b"
    ],
    "considering": [
        r"\bthinking about\b", r"\bconsidering\b", r"\bmight try\b",
        r"\bwould you recommend\b", r"\bshould i get\b", r"\bworth it\b"
    ],
    "browsing": [
        r"\bjust looking\b", r"\bbrowsing\b", r"\bwhat products\b",
        r"\btell me about\b", r"\bwhat do you have\b"
    ],
}

# Products to detect
REROOTS_PRODUCTS = [
    "AURA-GEN System", "AURA-GEN Rich Cream", "AURA-GEN Serum",
    "ACRC Rich Cream", "ARC Serum", "La Vela Bianca"
]


# ═══════════════════════════════════════════════════════════════════
# EXTRACTION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def extract_skin_type(text: str) -> Optional[str]:
    """Extract skin type from conversation text."""
    text_lower = text.lower()
    for skin_type, patterns in SKIN_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return skin_type
    return None


def extract_skin_concerns(text: str) -> List[str]:
    """Extract skin concerns from conversation text."""
    text_lower = text.lower()
    concerns = []
    for concern, patterns in SKIN_CONCERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                concerns.append(concern)
                break
    return concerns


def extract_allergies(text: str) -> List[str]:
    """Extract mentioned allergies or sensitivities."""
    text_lower = text.lower()
    allergies = []
    for pattern in ALLERGY_PATTERNS:
        matches = re.findall(pattern, text_lower)
        allergies.extend(matches)
    return list(set(allergies))


def extract_purchase_intent(text: str) -> str:
    """Determine purchase intent level."""
    text_lower = text.lower()
    for intent, patterns in PURCHASE_INTENT_SIGNALS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return intent
    return "none"


def extract_products_mentioned(text: str) -> List[str]:
    """Extract Reroots products mentioned in conversation."""
    text_lower = text.lower()
    mentioned = []
    for product in REROOTS_PRODUCTS:
        if product.lower() in text_lower:
            mentioned.append(product)
    return mentioned


def extract_age_range(text: str) -> Optional[str]:
    """Extract age range from conversation."""
    text_lower = text.lower()
    
    # Direct age mentions
    age_match = re.search(r"\b(\d{2})\s*(?:years? old|yo)\b", text_lower)
    if age_match:
        age = int(age_match.group(1))
        if age < 20:
            return "teen"
        elif age < 30:
            return "20s"
        elif age < 40:
            return "30s"
        elif age < 50:
            return "40s"
        else:
            return "50+"
    
    # Indirect mentions
    if any(w in text_lower for w in ["teenager", "teen skin", "high school"]):
        return "teen"
    if any(w in text_lower for w in ["in my 20s", "early 20s", "late 20s", "mid 20s"]):
        return "20s"
    if any(w in text_lower for w in ["in my 30s", "early 30s", "late 30s", "mid 30s"]):
        return "30s"
    if any(w in text_lower for w in ["in my 40s", "early 40s", "late 40s", "mid 40s"]):
        return "40s"
    if any(w in text_lower for w in ["in my 50s", "over 50", "mature skin", "menopause"]):
        return "50+"
    
    return None


# ═══════════════════════════════════════════════════════════════════
# PROFILE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

class CustomerMemory:
    """Manages customer profile extraction and retrieval."""
    
    def __init__(self, db):
        self.db = db
        self.collection_name = "reroots_customer_profiles"
    
    async def get_profile(self, customer_id: str, user_email: Optional[str] = None) -> Dict[str, Any]:
        """
        Get customer profile by ID (phone number or session-based ID).
        
        CROSS-DEVICE MEMORY: If user_email is provided, prioritizes the
        account-based profile (email-keyed) over session-based profile.
        This allows returning users to access their conversation memory
        from any device.
        
        Args:
            customer_id: Session-based ID (session_{hash})
            user_email: Optional logged-in user's email for cross-device memory
            
        Returns:
            Customer profile dict (empty profile if not found)
        """
        profile = None
        
        # Priority 1: Look up by email (cross-device memory)
        if user_email:
            profile = await self.db[self.collection_name].find_one(
                {"account_email": user_email.lower()},
                {"_id": 0}
            )
            if profile:
                logger.info(f"CustomerMemory: Loaded ACCOUNT profile for {user_email[:8]}...")
                return profile
        
        # Priority 2: Look up by session-based customer_id
        profile = await self.db[self.collection_name].find_one(
            {"customer_id": customer_id},
            {"_id": 0}
        )
        
        if profile:
            logger.info(f"CustomerMemory: Loaded SESSION profile for {customer_id[:8]}...")
            return profile
        
        return {**EMPTY_PROFILE, "customer_id": customer_id}
    
    async def link_session_to_account(
        self,
        session_id: str,
        user_email: str,
        user_id: str,
        user_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Link a chat session to a logged-in user account.
        
        CROSS-DEVICE MEMORY: When a user logs in, we:
        1. Find their existing account profile (by email)
        2. Find their current session profile (by session_id)
        3. Merge session data into account profile
        4. Return the merged profile for continued personalization
        
        Args:
            session_id: Current chat session ID
            user_email: User's email from JWT token
            user_id: User's ID from JWT token
            user_name: User's display name (optional)
            
        Returns:
            Merged customer profile
        """
        email = user_email.lower()
        session_customer_id = f"session_{session_id[:32]}"
        
        logger.info(f"CustomerMemory: Linking session {session_id[:8]}... to account {email}")
        
        # Get existing account profile
        account_profile = await self.db[self.collection_name].find_one(
            {"account_email": email},
            {"_id": 0}
        )
        
        # Get current session profile
        session_profile = await self.db[self.collection_name].find_one(
            {"customer_id": session_customer_id},
            {"_id": 0}
        )
        
        # Base profile (start with account or create new)
        if account_profile:
            merged = account_profile.copy()
        else:
            merged = {
                **EMPTY_PROFILE,
                "customer_id": f"account_{email}",
                "account_email": email,
                "user_id": user_id,
                "user_name": user_name,
                "first_seen": datetime.now(timezone.utc)
            }
        
        # Merge session data into account profile if session exists
        if session_profile:
            # Merge concerns (union)
            existing_concerns = set(merged.get("skin_concerns", []))
            session_concerns = set(session_profile.get("skin_concerns", []))
            merged["skin_concerns"] = list(existing_concerns | session_concerns)
            
            # Merge allergies (union)
            existing_allergies = set(merged.get("allergies", []))
            session_allergies = set(session_profile.get("allergies", []))
            merged["allergies"] = list(existing_allergies | session_allergies)
            
            # Merge products mentioned/interested (union)
            existing_products = set(merged.get("products_mentioned", []))
            session_products = set(session_profile.get("products_mentioned", []))
            merged["products_mentioned"] = list(existing_products | session_products)
            
            existing_interested = set(merged.get("products_interested", []))
            session_interested = set(session_profile.get("products_interested", []))
            merged["products_interested"] = list(existing_interested | session_interested)
            
            # Update skin type if session has it and account doesn't
            if session_profile.get("skin_type") and not merged.get("skin_type"):
                merged["skin_type"] = session_profile["skin_type"]
            
            # Update age range if session has it and account doesn't
            if session_profile.get("age_range") and not merged.get("age_range"):
                merged["age_range"] = session_profile["age_range"]
            
            # Upgrade purchase intent (never downgrade)
            intent_levels = {"none": 0, "browsing": 1, "considering": 2, "ready": 3}
            session_intent = session_profile.get("purchase_intent", "none")
            account_intent = merged.get("purchase_intent", "none")
            if intent_levels.get(session_intent, 0) > intent_levels.get(account_intent, 0):
                merged["purchase_intent"] = session_intent
            
            # Increment interaction count
            merged["interaction_count"] = (
                merged.get("interaction_count", 0) + 
                session_profile.get("interaction_count", 0)
            )
            
            # Use earliest first_seen
            session_first = session_profile.get("first_seen")
            if session_first:
                account_first = merged.get("first_seen")
                if not account_first or (isinstance(session_first, datetime) and isinstance(account_first, datetime) and session_first < account_first):
                    merged["first_seen"] = session_first
            
            # Delete the session-based profile after merging
            await self.db[self.collection_name].delete_one({"customer_id": session_customer_id})
            logger.info(f"CustomerMemory: Deleted session profile {session_customer_id[:8]}... after merge")
        
        # Update metadata
        merged["last_seen"] = datetime.now(timezone.utc)
        merged["account_email"] = email
        merged["user_id"] = user_id
        if user_name:
            merged["user_name"] = user_name
        
        # Track linked sessions
        linked_sessions = merged.get("linked_sessions", [])
        if session_id not in linked_sessions:
            linked_sessions.append(session_id)
            merged["linked_sessions"] = linked_sessions[-10:]  # Keep last 10
        
        # Save merged profile (upsert by email)
        await self.db[self.collection_name].update_one(
            {"account_email": email},
            {"$set": merged},
            upsert=True
        )
        
        logger.info(f"CustomerMemory: Account profile updated for {email}")
        
        return merged
    
    async def get_profile_by_email(self, user_email: str) -> Dict[str, Any]:
        """
        Get customer profile by email (for cross-device memory).
        
        Args:
            user_email: User's email address
            
        Returns:
            Customer profile or empty profile
        """
        email = user_email.lower()
        
        profile = await self.db[self.collection_name].find_one(
            {"account_email": email},
            {"_id": 0}
        )
        
        if profile:
            logger.info(f"CustomerMemory: Loaded profile by email for {email[:8]}...")
            return profile
        
        return {**EMPTY_PROFILE, "account_email": email}
    
    async def extract_and_update(
        self,
        customer_id: str,
        conversation_text: str,
        session_id: str = None,
        user_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract information from conversation and update profile.
        
        CROSS-DEVICE MEMORY: If user_email is provided, updates the
        account-based profile instead of session-based profile.
        
        Args:
            customer_id: Unique customer identifier (phone or session hash)
            conversation_text: Full conversation text to analyze
            session_id: Optional session ID for tracking
            user_email: Optional logged-in user's email for cross-device memory
        
        Returns:
            Updated customer profile
        """
        # Get existing profile (prioritize account-based if email provided)
        profile = await self.get_profile(customer_id, user_email)
        
        # Extract new information
        new_skin_type = extract_skin_type(conversation_text)
        new_concerns = extract_skin_concerns(conversation_text)
        new_allergies = extract_allergies(conversation_text)
        new_intent = extract_purchase_intent(conversation_text)
        new_products = extract_products_mentioned(conversation_text)
        new_age_range = extract_age_range(conversation_text)
        
        # Update profile with new information (preserve existing if no new data)
        updates = {}
        
        if new_skin_type:
            updates["skin_type"] = new_skin_type
        
        if new_concerns:
            existing_concerns = set(profile.get("skin_concerns", []))
            existing_concerns.update(new_concerns)
            updates["skin_concerns"] = list(existing_concerns)
        
        if new_allergies:
            existing_allergies = set(profile.get("allergies", []))
            existing_allergies.update(new_allergies)
            updates["allergies"] = list(existing_allergies)
        
        # Update purchase intent (only upgrade, don't downgrade)
        intent_levels = {"none": 0, "browsing": 1, "considering": 2, "ready": 3}
        current_intent = profile.get("purchase_intent", "none")
        if intent_levels.get(new_intent, 0) > intent_levels.get(current_intent, 0):
            updates["purchase_intent"] = new_intent
        
        if new_products:
            existing_products = set(profile.get("products_mentioned", []))
            existing_products.update(new_products)
            updates["products_mentioned"] = list(existing_products)
            
            # If showing purchase intent, add to interested products
            if new_intent in ["considering", "ready"]:
                interested = set(profile.get("products_interested", []))
                interested.update(new_products)
                updates["products_interested"] = list(interested)
        
        if new_age_range:
            updates["age_range"] = new_age_range
        
        # Update metadata
        updates["last_seen"] = datetime.now(timezone.utc)
        updates["interaction_count"] = profile.get("interaction_count", 0) + 1
        
        if not profile.get("first_seen"):
            updates["first_seen"] = datetime.now(timezone.utc)
        
        # Save to database - use email-based key if available for cross-device memory
        if updates:
            if user_email:
                # Update account-based profile (cross-device memory)
                await self.db[self.collection_name].update_one(
                    {"account_email": user_email.lower()},
                    {
                        "$set": updates,
                        "$setOnInsert": {"account_email": user_email.lower()}
                    },
                    upsert=True
                )
                logger.info(f"CustomerMemory: Updated ACCOUNT profile for {user_email[:8]}... with {list(updates.keys())}")
            else:
                # Update session-based profile
                await self.db[self.collection_name].update_one(
                    {"customer_id": customer_id},
                    {
                        "$set": updates,
                        "$setOnInsert": {"customer_id": customer_id}
                    },
                    upsert=True
                )
                logger.info(f"CustomerMemory: Updated SESSION profile for {customer_id[:8]}... with {list(updates.keys())}")
        
        # Return merged profile
        profile.update(updates)
        return profile
    
    def generate_personalization_context(self, profile: Dict[str, Any]) -> str:
        """
        Generate context string to inject into AI system prompt.
        Uses TOON format for efficient LLM token usage.
        """
        if not profile or profile.get("interaction_count", 0) == 0:
            return ""
        
        # Build profile dict for TOON conversion (exclude empty/None values)
        profile_data = {}
        
        if profile.get("skin_type"):
            profile_data["skin_type"] = profile["skin_type"]
        
        if profile.get("skin_concerns"):
            profile_data["concerns"] = ", ".join(profile["skin_concerns"])
        
        if profile.get("allergies"):
            profile_data["ALLERGIES"] = ", ".join(profile["allergies"]) + " (NEVER recommend)"
        
        if profile.get("age_range"):
            profile_data["age_range"] = profile["age_range"]
        
        if profile.get("products_mentioned"):
            profile_data["asked_about"] = ", ".join(profile["products_mentioned"])
        
        if profile.get("products_interested"):
            profile_data["interested_in"] = ", ".join(profile["products_interested"])
        
        if profile.get("purchase_intent") and profile["purchase_intent"] != "none":
            intent_map = {
                "browsing": "browsing",
                "considering": "considering_purchase",
                "ready": "ready_to_buy"
            }
            profile_data["intent"] = intent_map.get(profile["purchase_intent"], profile["purchase_intent"])
        
        visits = profile.get("interaction_count", 0)
        if visits > 1:
            profile_data["visits"] = visits
        
        if not profile_data:
            return ""
        
        # Convert to TOON format
        toon_context = json_to_toon(profile_data, "CustomerProfile")
        
        return f"--- CUSTOMER PROFILE ---\n{toon_context}\n\nPersonalize responses based on this profile."


# ═══════════════════════════════════════════════════════════════════
# LLM-BASED EXTRACTION (for complex extraction)
# ═══════════════════════════════════════════════════════════════════

async def extract_with_llm(conversation_text: str) -> Dict[str, Any]:
    """
    Use LLM to extract customer profile information from conversation.
    More accurate but slower than regex-based extraction.
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            logger.warning("CustomerMemory: No LLM key for advanced extraction")
            return {}
        
        system_prompt = """You are a customer profile extractor. Analyze the conversation and extract:
1. skin_type: dry, oily, combination, sensitive, or normal
2. skin_concerns: list of concerns (acne, wrinkles, dark_spots, redness, dullness, etc.)
3. allergies: list of ingredients or substances to avoid
4. age_range: teen, 20s, 30s, 40s, or 50+
5. purchase_intent: none, browsing, considering, or ready

Return ONLY valid JSON with these fields. Use null for unknown values, empty arrays for no items.
Example: {"skin_type": "dry", "skin_concerns": ["wrinkles", "dullness"], "allergies": [], "age_range": "40s", "purchase_intent": "considering"}"""

        chat = LlmChat(
            api_key=api_key,
            session_id="extraction_temp",
            system_message=system_prompt
        )
        chat.with_model("openai", "gpt-4o-mini")  # Fast and cheap for extraction
        
        response = await chat.send_message(UserMessage(text=f"Extract profile from:\n{conversation_text[:2000]}"))
        
        # Parse JSON response
        json_match = re.search(r'\{[^}]+\}', response)
        if json_match:
            return json.loads(json_match.group())
        
        return {}
        
    except Exception as e:
        logger.error(f"CustomerMemory: LLM extraction failed: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════

_memory_instance: Optional[CustomerMemory] = None


def get_customer_memory(db) -> CustomerMemory:
    """Get or create the CustomerMemory singleton."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = CustomerMemory(db)
    return _memory_instance
