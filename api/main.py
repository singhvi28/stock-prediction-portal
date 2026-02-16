from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import jwt
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_db, init_db, User, PasswordResetToken
from utils import hash_password, verify_password, generate_reset_token, send_email, verify_token, get_current_user
from dotenv import load_dotenv

load_dotenv()

# Lifespan context for DB initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include payment router
from payment import router as payment_router
app.include_router(payment_router)

# Models
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

from pydantic import BaseModel, field_validator

class TickerRequest(BaseModel):
    ticker: str
    lookback: Optional[int] = 100
    train_size: Optional[int] = 1000
    model: Optional[str] = "multihead"

    @field_validator('ticker')
    def validate_ticker(cls, v):
        if not v or not v.strip():
             raise ValueError('Ticker cannot be empty')
        # Simple check for alphanumeric or standard format
        if not v.isalnum() and not all(c.isalnum() or c in "-." for c in v):
             raise ValueError('Invalid ticker format')
        return v

    @field_validator('lookback')
    def validate_lookback(cls, v):
        if v is not None and v <= 0:
             raise ValueError('Lookback must be positive')
        return v
        
    @field_validator('model')
    def validate_model(cls, v):
        allowed = ["multihead", "additive", "lstm"]
        if v and v not in allowed:
             raise ValueError(f'Model must be one of {allowed}')
        return v

# Helper functions
from utils import create_access_token

# Routes

# Routes

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == request.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    hashed_pwd = hash_password(request.password)
    new_user = User(email=request.email, password_hash=hashed_pwd)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()
    
    if not user:
        # Don't reveal user existence
        return {"message": "If this email is registered, you will receive a reset link."}
    
    token = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    reset_token = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
    
    recipient_email = user.email
    db.add(reset_token)
    await db.commit()
    
    # Send email
    send_email(recipient_email, "Password Reset", token)
    
    return {"message": "If this email is registered, you will receive a reset link."}

@app.post("/api/auth/reset-password")
async def reset_password(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == request.token))
    reset_token_entry = result.scalars().first()
    
    if not reset_token_entry:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if reset_token_entry.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
    
    # Update password
    result = await db.execute(select(User).where(User.id == reset_token_entry.user_id))
    user = result.scalars().first()
    
    if not user:
         raise HTTPException(status_code=400, detail="User not found")

    user.password_hash = hash_password(request.new_password)
    
    # clear token
    await db.delete(reset_token_entry)
    await db.commit()
    
    return {"message": "Password updated successfully"}

@app.get("/api/auth/verify")
async def verify(email: str = Depends(verify_token)):
    return {"email": email, "authenticated": True}

@app.get("/api/auth/me")
async def get_current_user_info(email: str = Depends(verify_token), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {
        "id": user.id,
        "email": user.email,
        "credits": user.credits
    }

from db import get_db, init_db, User, PasswordResetToken, PredictionHistory, CreditLedger
from sqlalchemy import extract, desc

# ... (other imports)

@app.post("/api/predict")
async def predict(request: TickerRequest, email: str = Depends(verify_token), db: AsyncSession = Depends(get_db)):
    """
    Endpoint to get stock predictions using LSTM with attention mechanism
    """
    try:
        # Get user ID
        # Lock the user row to prevent race conditions on credit deduction
        print(f"DEBUG: Processing request for {email}")
        result = await db.execute(select(User).where(User.email == email).with_for_update())
        user = result.scalars().first()
        if not user:
             print("DEBUG: User not found")
             raise HTTPException(status_code=401, detail="User not found")

        print(f"DEBUG: User {user.email} credits {user.credits} locked.")

        # Validate Model and Cost
        model_type = request.model or "multihead"
        cost = 3 if model_type == "additive" else 2
        
        # Check Credits
        if user.credits < cost:
            print(f"DEBUG: Insufficient credits. Has {user.credits}, needs {cost}")
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient credits. {cost} credits required."
            )
        
        # Deduct Credits
        user.credits -= cost
        print(f"DEBUG: Deducted {cost}. New balance {user.credits}")
        ledger = CreditLedger(
            user_id=user.id,
            amount=-cost,
            reason=f"PREDICTION_{model_type.upper()}"
        )
        db.add(ledger)
        await db.commit()
        print("DEBUG: Commit done")
        
        # Dispatch Task
        import uuid
        task_id = str(uuid.uuid4())
        
        # Create PredictionHistory record immediately to establish ownership
        # We initialize with basic info. processing_data/results will be updated by worker.
        history = PredictionHistory(
            user_id=user.id,
            task_id=task_id,
            ticker=request.ticker.upper(),
            model_type=model_type,
            # accurate/prediction_data are null initially
        )
        db.add(history)
        await db.commit()
        
        from tasks import predict_task
        # Pass the pre-generated task_id to Celery
        predict_task.apply_async(
            args=[request.ticker, model_type, request.lookback, user.id],
            task_id=task_id
        )
        
        return {"task_id": task_id, "status": "processing"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@app.get("/api/predict/{task_id}")
async def get_prediction_status(
    task_id: str, 
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Check Ownership in DB
    # We query PredictionHistory to see if this task belongs to the user
    stmt = select(PredictionHistory).where(PredictionHistory.task_id == task_id)
    result = await db.execute(stmt)
    history = result.scalars().first()
    
    if not history:
        # If not found in DB, it might be an invalid ID or very old task.
        # But for security, if we can't verify owner, we must deny or return 404.
        raise HTTPException(status_code=404, detail="Task not found")
        
    if history.user_id != user.id:
        print(f"DEBUG: IDOR Attempt! User {user.id} tried to access task {task_id} owned by {history.user_id}")
        raise HTTPException(status_code=403, detail="Not authorized to view this task")

    # 2. Fetch Status from Celery
    from celery.result import AsyncResult
    from worker import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    
    if result.state == "SUCCESS":
        return {"status": "completed", "result": result.result}
    elif result.state == "FAILURE":
        return {"status": "failed", "error": str(result.result)}
    else:
        return {"status": "processing"}

@app.get("/api/history")
async def get_history(
    page: int = 1, 
    limit: int = 50, 
    ticker: Optional[str] = None,
    model: Optional[str] = None,
    email: str = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Use with_for_update() to lock the row for the duration of the transaction
    query = select(User).where(User.email == email).with_for_update()
    result = await db.execute(query)
    user = result.scalars().first()
    if not user:
         raise HTTPException(status_code=401, detail="User not found")

    query = select(PredictionHistory).where(PredictionHistory.user_id == user.id)
    
    if ticker:
        query = query.where(PredictionHistory.ticker.ilike(f"%{ticker}%"))
    
    if model:
        query = query.where(PredictionHistory.model_type == model)
    
    # Order by newest first
    query = query.order_by(desc(PredictionHistory.created_at))
    
    # Pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    history = result.scalars().all()
    
    return [
        {
            "id": h.id,
            "ticker": h.ticker,
            "model_type": h.model_type,
            "directional_accuracy": h.directional_accuracy,
            "created_at": h.created_at,
            "prediction_data": h.prediction_data
        }
        for h in history
    ]

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    # Enforce localhost to match potential connection assumptions but 0.0.0.0 is safer for containers
    uvicorn.run(app, host="0.0.0.0", port=8000)
