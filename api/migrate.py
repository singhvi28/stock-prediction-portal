import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL").replace("+asyncpg", "")

async def migrate():
    print(f"Connecting to {DATABASE_URL}")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    try:
        # 1. Add credits to users
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER DEFAULT 5")
            print("Added credits column to users table.")
        except Exception as e:
            print(f"Error altering users table: {e}")

        # 2. Create transactions table
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    razorpay_order_id VARCHAR UNIQUE NOT NULL,
                    razorpay_payment_id VARCHAR UNIQUE,
                    amount_paise INTEGER NOT NULL,
                    credits INTEGER NOT NULL,
                    status VARCHAR DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS ix_transactions_id ON transactions(id);
                CREATE INDEX IF NOT EXISTS ix_transactions_user_id ON transactions(user_id);
                CREATE INDEX IF NOT EXISTS ix_transactions_razorpay_order_id ON transactions(razorpay_order_id);
                CREATE INDEX IF NOT EXISTS ix_transactions_razorpay_payment_id ON transactions(razorpay_payment_id);
            """)
            print("Created transactions table.")
        except Exception as e:
            print(f"Error creating transactions table: {e}")

        # 3. Create credit_ledger table
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS credit_ledger (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    transaction_id INTEGER REFERENCES transactions(id),
                    amount INTEGER NOT NULL,
                    reason VARCHAR NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS ix_credit_ledger_id ON credit_ledger(id);
                CREATE INDEX IF NOT EXISTS ix_credit_ledger_user_id ON credit_ledger(user_id);
            """)
            print("Created credit_ledger table.")
        except Exception as e:
            print(f"Error creating credit_ledger table: {e}")

    finally:
        await conn.close()
    
    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
