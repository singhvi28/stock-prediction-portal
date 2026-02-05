import streamlit as st
from datetime import datetime
import api_client
import components

def render_auth_page():
    st.title("🔐 Access Portal")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Forgot Password"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            pwd = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if api_client.login(email, pwd):
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
                    success, msg = api_client.register(r_email, r_pwd)
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
                    success, msg = api_client.forgot_password(f_email)
                    if success:
                        st.info(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Please enter your email")

def show_history_page():
    st.title("📜 Prediction History")
    
    # Filter Controls
    col1, col2 = st.columns(2)
    with col1:
        month = st.selectbox("Month", range(1, 13), index=datetime.now().month-1, format_func=lambda x: datetime(2000, x, 1).strftime('%B'))
    with col2:
        year = st.number_input("Year", min_value=2024, max_value=datetime.now().year, value=datetime.now().year)

    # Fetch History
    history = api_client.fetch_history(month, year, limit=20)
    
    if history is not None:
        if not history:
            st.info("No prediction history found for this period.")
            return

        # Display History List
        for item in history:
            timestamp = datetime.fromisoformat(item['created_at'])
            with st.expander(f"{item['ticker']} - {timestamp.strftime('%Y-%m-%d %H:%M')} ({item['model_type']})"):
                # Quick Metrics
                data = item['prediction_data']
                if 'metrics' in data:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("RMSE", f"${data['metrics']['rmse']:.2f}")
                    m2.metric("MAE", f"${data['metrics']['mae']:.2f}")
                    m3.metric("MAPE", f"{data['metrics']['mape']:.2f}%")
                    m4.metric("Directional Accuracy", f"{data['metrics']['directional_accuracy']:.2f}%")
                
                # Store selected data in session state to visualize
                if st.button("Load Visualization", key=f"btn_{item['id']}"):
                        components.visualize_prediction(data, show_metrics=False)

def render_dashboard():
    st.title(f"Analysis for {st.session_state.get('last_ticker', 'Stock')}")
    
    st.sidebar.title("📈 Controls")
    ticker = st.sidebar.text_input("Stock Ticker", value="AAPL").upper()
    lookback = 60
    
    model_choice = st.sidebar.selectbox(
        "Prediction Model",
        ["Multihead Attention", "Additive Attention"]
    )
    
    model_map = {
        "Multihead Attention": "multihead",
        "Additive Attention": "additive"
    }
    
    if st.sidebar.button("Run Prediction & Forecast"):
        # Save last ticker for title
        st.session_state.last_ticker = ticker
        
        result = api_client.get_prediction(ticker, lookback, model_map[model_choice])
        if result:
            components.visualize_prediction(result)
