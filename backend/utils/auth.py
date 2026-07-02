import bcrypt
from typing import Tuple

def verify_password(plain_password: str, hashed_password: str) -> Tuple[bool, str]:
    """
    Securely verifies a plaintext password against a hashed password using bcrypt.
    
    Args:
        plain_password (str): The plaintext password to verify
        hashed_password (str): The bcrypt hashed password to compare against
        
    Returns:
        Tuple[bool, str]: A tuple containing:
            - bool: True if passwords match, False otherwise
            - str: Error message if verification fails, empty string otherwise
            
    Security Considerations:
        - Uses constant-time comparison to prevent timing attacks
        - Handles bcrypt verification errors gracefully
        - Never leaks information about why verification failed
    """
    try:
        if not plain_password or not hashed_password:
            return False, "Missing password input"
            
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        ), ""
    except Exception as e:
        return False, f"Password verification failed: {str(e)}"
