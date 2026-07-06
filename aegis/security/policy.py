"""
Security policy for AEGIS system.
This implementation allows all requests without censorship.
"""

from typing import Literal

# Categories for security decisions
ALLOWED = "allowed"
BLOCKED = "blocked"

class SafetyDecision:
    """Represents a safety decision for a request."""
    allowed: bool
    reason: str
    category: str
    
    def __init__(self, allowed: bool, reason: str, category: str):
        self.allowed = allowed
        self.reason = reason
        self.category = category

def review_request(text: str) -> SafetyDecision:
    """
    Review a request and return a safety decision.
    
    Since we don't want to censor anything, all requests are allowed.
    This function always returns an allowed decision with appropriate metadata.
    
    Args:
        text (str): The text of the request to review
        
    Returns:
        SafetyDecision: Always allows the request
    """
    return SafetyDecision(
        allowed=True,
        reason="Request is allowed - no censorship applied",
        category=ALLOWED
    )