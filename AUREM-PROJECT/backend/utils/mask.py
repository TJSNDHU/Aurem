"""
Data Masking Utilities for Reroots
Provides masking functions for sensitive data in admin views.
Real data is stored in DB - only masked on display.
"""

import re
from typing import Optional


def mask_phone(phone: Optional[str]) -> str:
    """
    Mask phone number for display.
    
    Input: +14168869408 or 4168869408 or (416) 886-9408
    Output: +1******9408 or ******9408
    
    Preserves country code and last 4 digits only.
    """
    if not phone:
        return ""
    
    # Remove all non-digit characters except leading +
    cleaned = re.sub(r'[^\d+]', '', str(phone))
    
    if not cleaned:
        return ""
    
    # Handle numbers with + prefix
    if cleaned.startswith('+'):
        prefix = '+'
        digits = cleaned[1:]
    else:
        prefix = ''
        digits = cleaned
    
    if len(digits) < 4:
        return '*' * len(digits)
    
    # Keep country code (first 1-2 digits) and last 4
    if len(digits) >= 11:
        # International format like +14168869408 (11+ digits)
        country_code = digits[:1]  # Just the country code
        last_four = digits[-4:]
        masked_middle = '*' * (len(digits) - 5)
        return f"{prefix}{country_code}{masked_middle}{last_four}"
    elif len(digits) >= 10:
        # Standard 10-digit format
        last_four = digits[-4:]
        masked_middle = '*' * (len(digits) - 4)
        return f"{prefix}{masked_middle}{last_four}"
    else:
        # Short number - just mask all but last 4
        last_four = digits[-4:]
        masked_middle = '*' * (len(digits) - 4)
        return f"{prefix}{masked_middle}{last_four}"


def mask_email(email: Optional[str]) -> str:
    """
    Mask email for display.
    
    Input: john.doe@example.com
    Output: j***e@example.com
    """
    if not email or '@' not in email:
        return email or ""
    
    local, domain = email.rsplit('@', 1)
    
    if len(local) <= 2:
        masked_local = '*' * len(local)
    else:
        masked_local = f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}"
    
    return f"{masked_local}@{domain}"


def mask_credit_card(card_number: Optional[str]) -> str:
    """
    Mask credit card number.
    
    Input: 4111111111111111
    Output: ****-****-****-1111
    """
    if not card_number:
        return ""
    
    # Remove non-digits
    digits = re.sub(r'\D', '', str(card_number))
    
    if len(digits) < 4:
        return '*' * len(digits)
    
    last_four = digits[-4:]
    return f"****-****-****-{last_four}"


def mask_ip(ip: Optional[str]) -> str:
    """
    Mask IP address for privacy.
    
    Input: 192.168.1.100
    Output: 192.168.***.***
    """
    if not ip:
        return ""
    
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.***.***"
    
    # IPv6 or other format - just mask half
    if len(ip) > 8:
        return f"{ip[:8]}***"
    
    return "***"


def unmask_for_export(masked_value: str, original_value: str) -> str:
    """
    For authorized exports, return the original unmasked value.
    Use only in authenticated admin contexts with audit logging.
    """
    return original_value
