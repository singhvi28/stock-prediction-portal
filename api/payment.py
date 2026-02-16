from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_db, Transaction, User
from utils import get_current_user
import razorpay
import os
from datetime import datetime
from tasks import process_payment

router = APIRouter(prefix="/payment", tags=["payment"])

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_placeholder")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "secret_placeholder")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "webhook_placeholder")

# Initialize client only if keys are present to avoid startup errors
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

class OrderRequest(BaseModel):
    credits: int

@router.post("/order")
async def create_order(req: OrderRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Rate: 1 Credit = 10 INR
    amount_inr = req.credits * 10
    amount_paise = amount_inr * 100
    
    currency = "INR"
    
    try:
        data = {"amount": amount_paise, "currency": currency, "receipt": f"receipt_user_{user.id}"}
        order = client.order.create(data=data)
        
        # Save Transaction
        txn = Transaction(
            user_id=user.id,
            razorpay_order_id=order['id'],
            amount_paise=amount_paise,
            credits=req.credits,
            status="PENDING"
        )
        db.add(txn)
        await db.commit()
        
        return {
            "order_id": order['id'], 
            "key_id": RAZORPAY_KEY_ID, 
            "amount": amount_paise, 
            "currency": currency,
            "name": "Stock Prediction Credits",
            "description": f"Purchase {req.credits} credits"
        }
    except Exception as e:
        print(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def payment_webhook(request: Request):
    # Verify Signature
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Signature")
        
    body = await request.body()
    
    try:
        client.utility.verify_webhook_signature(
            body.decode(), 
            signature, 
            RAZORPAY_WEBHOOK_SECRET
        )
    except Exception as e:
        print(f"Signature Verification Failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid Signature")

    event = await request.json()
    
    if event.get("event") == "payment.captured":
        payment = event["payload"]["payment"]["entity"]
        order_id = payment["order_id"]
        payment_id = payment["id"]
        
        # Push to Celery
        print(f"Received payment {payment_id} for order {order_id}. Queuing task.")
        process_payment.delay(payment_id, order_id)

    return {"status": "ok"}

class VerificationRequest(BaseModel):
    payment_id: str
    order_id: str
    signature: str

@router.post("/verify")
async def verify_payment(req: VerificationRequest):
    try:
        # 1. Verify Signature
        client.utility.verify_payment_signature({
            'razorpay_order_id': req.order_id,
            'razorpay_payment_id': req.payment_id,
            'razorpay_signature': req.signature
        })
        
        # 2. Check status (Optional but recommended)
        payment = client.payment.fetch(req.payment_id)
        if payment['status'] != 'captured':
             print(f"Payment {req.payment_id} is {payment['status']}, not captured.")
             raise HTTPException(status_code=400, detail="Payment not captured")

        # 3. Trigger Task
        print(f"Verified payment {req.payment_id}. Queuing task.")
        process_payment.delay(req.payment_id, req.order_id)
        
        return {"status": "verified"}
        
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Signature")
    except Exception as e:
        print(f"Verification Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
