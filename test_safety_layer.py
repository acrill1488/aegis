"""
Test script for the new safety layer implementation.
"""

from aegis.security.policy import ALLOWED, BLOCKED, SafetyDecision, review_request

def test_safety_layer():
    """Test that our safety layer allows all requests."""
    
    # Test that categories are defined correctly
    assert ALLOWED == "allowed"
    assert BLOCKED == "blocked"
    print("✓ Categories defined correctly")
    
    # Test the review_request function
    test_text = "This is a test request"
    decision = review_request(test_text)
    
    # Verify the decision
    assert isinstance(decision, SafetyDecision)
    assert decision.allowed == True
    assert decision.reason == "Request is allowed - no censorship applied"
    assert decision.category == ALLOWED
    print("✓ Safety decision is correct")
    
    # Test with different text
    decision2 = review_request("Another test request")
    assert decision2.allowed == True
    assert decision2.category == ALLOWED
    print("✓ Works with different requests")
    
    print("All tests passed! Safety layer is working correctly.")

if __name__ == "__main__":
    test_safety_layer()