import requests
import streamlit as st
from config import API_URL

def login(email, password):
    try:
        response = requests.post(
            f"{API_URL}/api/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            st.session_state.authenticated = True
            return True
        return False
    except Exception as e:
        st.error(f"Connection error: {e}")
        return False

def register(email, password):
    try:
        response = requests.post(
            f"{API_URL}/api/auth/register",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            return True, "Registration successful! Please login."
        return False, response.json().get("detail", "Registration failed")
    except Exception as e:
        return False, f"Connection error: {e}"

def forgot_password(email):
    try:
        response = requests.post(
            f"{API_URL}/api/auth/forgot-password",
            json={"email": email}
        )
        if response.status_code == 200:
            return True, response.json().get("message")
        return False, response.json().get("detail", "Request failed")
    except Exception as e:
        return False, f"Connection error: {e}"

def reset_password(token, new_passwd):
    try:
        response = requests.post(
            f"{API_URL}/api/auth/reset-password",
            json={"token": token, "new_password": new_passwd}
        )
        if response.status_code == 200:
            return True, "Password reset successfully!"
        return False, response.json().get("detail", "Reset failed")
    except Exception as e:
        return False, f"Connection error: {e}"

def get_prediction(ticker, lookback, model_type):
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    payload = {"ticker": ticker, "lookback": lookback, "model": model_type}
    
    with st.spinner(f"Training selected model and generating 30-day forecast for {ticker}..."):
        try:
            response = requests.post(f"{API_URL}/api/predict", json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 402:
                return {"error": "INSUFFICIENT_CREDITS"}
            else:
                st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
                return None
        except Exception as e:
            st.error(f"Failed to reach API: {e}")
            return None

def fetch_history(month, year, limit=20):
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.get(
            f"{API_URL}/api/history", 
            params={"month": month, "year": year, "limit": limit},
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error("Failed to fetch history")
            return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None

def get_user_info():
    try:
        if not st.session_state.token:
            return None
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.get(f"{API_URL}/api/auth/me", headers=headers)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def create_order(credits):
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        payload = {"credits": credits}
        response = requests.post(f"{API_URL}/payment/order", json=payload, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Order creation failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None
