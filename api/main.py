from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
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

class TickerRequest(BaseModel):
    ticker: str
    lookback: Optional[int] = 100
    train_size: Optional[int] = 1000
    model: Optional[str] = "multihead"

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
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    
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
        
    if reset_token_entry.expires_at < datetime.utcnow():
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
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
             raise HTTPException(status_code=401, detail="User not found")

        # Validate Model and Cost
        model_type = request.model or "multihead"
        cost = 3 if model_type == "additive" else 2
        
        # Check Credits
        if user.credits < cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient credits. {cost} credits required."
            )
        
        # Deduct Credits
        user.credits -= cost
        ledger = CreditLedger(
            user_id=user.id,
            amount=-cost,
            reason=f"PREDICTION_{model_type.upper()}"
        )
        db.add(ledger)
        await db.commit()
        
        try:
            if request.model == "additive":
                from prediction_service_additive import get_stock_predictions
            else:
                from prediction_service_multihead import get_stock_predictions
            
            lookback = request.lookback if request.lookback else 60
            result_data = get_stock_predictions(request.ticker.upper(), lookback=lookback, epochs=15)
            
            if "error" in result_data:
                raise Exception(result_data["error"])
            
            # Save to history
            acc = result_data.get('metrics', {}).get('directional_accuracy')
            
            history_entry = PredictionHistory(
                user_id=user.id,
                ticker=request.ticker.upper(),
                model_type=model_type,
                directional_accuracy=acc,
                prediction_data=result_data
            )
            db.add(history_entry)
            await db.commit()
            
            return result_data
            
        except Exception as e:
            # Refund on failure
            user.credits += cost
            refund_ledger = CreditLedger(
                user_id=user.id,
                amount=cost,
                reason=f"REFUND_FAILED_PREDICTION"
            )
            db.add(refund_ledger)
            await db.commit()
            
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Prediction failed: {str(e)}"
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@app.get("/api/history")
async def get_history(
    page: int = 1, 
    limit: int = 10, 
    month: Optional[int] = None, 
    year: Optional[int] = None,
    email: str = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user:
         raise HTTPException(status_code=401, detail="User not found")

    query = select(PredictionHistory).where(PredictionHistory.user_id == user.id)
    
    if month and year:
        query = query.where(extract('month', PredictionHistory.created_at) == month)
        query = query.where(extract('year', PredictionHistory.created_at) == year)
    
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
