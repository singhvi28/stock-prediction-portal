import streamlit as st
import requests
import plotly.graph_objects as go
import pandas as pd

# Configuration
API_URL = "http://localhost:8000"

st.set_page_config(page_title="Stock Prediction Dashboard", layout="wide")

def render_footer():
    st.markdown(
        """
        <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #0e1117;
            color: #9aa0a6;
            text-align: center;
            padding: 10px;
            font-size: 13px;
            z-index: 9999;
        }
        </style>

        <div class="footer">
            ⚠️ This dashboard is for educational and research purposes only.  
            It is not financial advice. Use at your own risk.
        </div>
        """,
        unsafe_allow_html=True,
    )

# Session State Initialization
if "token" not in st.session_state:
    st.session_state.token = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

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

def get_prediction(ticker, lookback, model_type):
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    payload = {"ticker": ticker, "lookback": lookback, "model": model_type}
    
    with st.spinner(f"Training selected model and generating 30-day forecast for {ticker}..."):
        try:
            response = requests.post(f"{API_URL}/api/predict", json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
                return None
        except Exception as e:
            st.error(f"Failed to reach API: {e}")
            return None

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

# --- UI LOGIC ---

# Check for reset token in URL
query_params = st.query_params
reset_token = query_params.get("token")

if reset_token:
    st.title("🔐 Reset Password")
    with st.form("reset_form"):
        new_p1 = st.text_input("New Password", type="password")
        new_p2 = st.text_input("Confirm Password", type="password")
        submit_reset = st.form_submit_button("Update Password")
        
        if submit_reset:
            if new_p1 != new_p2:
                st.error("Passwords do not match")
            else:
                success, msg = reset_password(reset_token, new_p1)
                if success:
                    st.success(msg)
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.error(msg)
    
elif not st.session_state.authenticated:
    st.title("🔐 Access Portal")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Forgot Password"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            pwd = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if login(email, pwd):
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    with tab2:
        with st.form("register_form"):
            r_email = st.text_input("Email")
            r_pwd = st.text_input("Password", type="password")
            r_submit = st.form_submit_button("Register")
            
            if r_submit:
                if r_email and r_pwd:
                    success, msg = register(r_email, r_pwd)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Please fill all fields")

    with tab3:
        st.write("Enter your email to receive a password reset token.")
        with st.form("forgot_form"):
            f_email = st.text_input("Email")
            f_submit = st.form_submit_button("Send Reset Link")
            
            if f_submit:
                if f_email:
                    success, msg = forgot_password(f_email)
                    if success:
                        st.info(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Please enter your email")
else:
    # Sidebar
    st.sidebar.title("📈 Controls")
    ticker = st.sidebar.text_input("Stock Ticker", value="AAPL").upper()
    
    # Fixed lookback window as per requirement
    lookback = 60
    
    # Model Selection
    model_choice = st.sidebar.selectbox(
        "Prediction Model",
        ["Multihead Attention", "Additive Attention"]
    )
    
    model_map = {
        "Multihead Attention": "multihead",
        "Additive Attention": "additive"
    }
    
    if st.sidebar.button("Run Prediction & Forecast"):
        result = get_prediction(ticker, lookback, model_map[model_choice])
        
        if result:
            st.title(f"Analysis for {result['ticker']}")
            
            # 1. Metrics Row
            if 'metrics' in result:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("RMSE", f"${result['metrics']['rmse']:.2f}")
                m2.metric("MAE", f"${result['metrics']['mae']:.2f}")
                m3.metric("MAPE", f"{result['metrics']['mape']:.2f}%")
                m4.metric("Directional Accuracy", f"{result['metrics']['directional_accuracy']:.2f}%")

            # 2. Main Forecast Plot
            st.markdown("### Price & Extended Forecast")
            
            historical_dates = result.get('historical_dates', [])
            historical_prices = result.get('historical_prices', [])
            model_historical_predictions = result.get('model_historical_predictions', [])
            forecast_dates = result.get('forecast_dates', [])
            forecast_prices = result.get('forecast_prices', [])
            
            # Create Plotly Graph
            fig = go.Figure()

            # Add Historical Data (Actual)
            fig.add_trace(go.Scatter(
                x=historical_dates,
                y=historical_prices,
                mode='lines',
                name='Actual Price',
                line=dict(color='#818cf8', width=2)
            ))

            # Add Historical Model Predictions
            if model_historical_predictions:
                 fig.add_trace(go.Scatter(
                    x=historical_dates,
                    y=model_historical_predictions,
                    mode='lines',
                    name='Model Fitted (Past)',
                    line=dict(color='#34d399', width=1.5, dash='dot'),
                    opacity=0.7
                ))

            # Add Forecast Data
            # Connect the last historical point to the first forecast point for continuity
            if historical_dates and model_historical_predictions and forecast_dates and forecast_prices:
                 # Prepend last model prediction to forecast for visual continuity
                viz_forecast_dates = [historical_dates[-1]] + forecast_dates
                viz_forecast_prices = [model_historical_predictions[-1]] + forecast_prices
                
                fig.add_trace(go.Scatter(
                    x=viz_forecast_dates,
                    y=viz_forecast_prices,
                    mode='lines',
                    name='Future Forecast',
                    line=dict(color='#fb923c', width=2, dash='dash')
                ))

            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color="#9aa0a6"),
                xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
                yaxis=dict(
                    showgrid=True, 
                    gridcolor='rgba(255,255,255,0.1)',
                    title="Price ($)"
                ),
                margin=dict(l=0, r=0, t=30, b=0),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                hovermode="x unified"
            )

            st.plotly_chart(fig, use_container_width=True)

    if st.sidebar.button("Logout"):
        st.session_state.token = None
        st.session_state.authenticated = False
        st.rerun()
    
    # Footer
    render_footer()