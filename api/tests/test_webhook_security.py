import pytest
import hmac
import hashlib
import json
from unittest.mock import patch, MagicMock
from db import Transaction

@pytest.mark.asyncio
async def test_webhook_invalid_signature(client):
    # Prepare payload
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_123456",
                    "order_id": "order_123456",
                    "amount": 50000,
                    "status": "captured"
                }
            }
        }
    }
    payload_str = json.dumps(payload)
    
    # Generate a BAD signature
    bad_signature = "invalid_signature_hash"
    
    # Send request with bad signature
    # Assuming endpoint is /api/payment/webhook and header is X-Razorpay-Signature
    headers = {
        "X-Razorpay-Signature": bad_signature,
        "Content-Type": "application/json"
    }
    
    # We need to ensure the webhook endpoint verifies signature BEFORE processing.
    # If the code uses Razorpay client to verify, it should raise SignatureVerificationError.
    
    # 3. Patch the verification utility
    # We want to ensure that if verification fails, the API returns 400.
    
    # We need to mock `razorpay.Client` instance or the method on it.
    # In payment.py: `client = razorpay.Client(...)`
    # And `client.utility.verify_webhook_signature(...)`
    
    # We can patch 'payment.client.utility.verify_webhook_signature'
    
    # We need to import SignatureVerificationError to raise it as side_effect
    from razorpay.errors import SignatureVerificationError

    with patch("payment.client.utility.verify_webhook_signature") as mock_verify:
        mock_verify.side_effect = SignatureVerificationError("Invalid Signature")
        
        response = await client.post(
            "/payment/webhook", 
            content=payload_str, 
            headers=headers
        )
        
        # 4. Verify Failure
        assert response.status_code == 400, f"Should return 400 on invalid signature, got {response.status_code}"
        assert tuple(response.json().values())[0] == "Invalid Signature"
