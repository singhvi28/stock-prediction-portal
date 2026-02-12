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
        ticker_input = st.text_input("Filter by Ticker", placeholder="e.g. AAPL").strip().upper()
    with col2:
        model_filter = st.selectbox("Filter by Model", ["All", "multihead", "additive"])

    if model_filter == "All":
        model_filter = None
        
    if ticker_input and not components.is_valid_ticker(ticker_input):
        st.warning("⚠️ Invalid ticker format. Only letters, numbers, '.', and '-' are allowed.")
        return

    # Fetch History
    history = api_client.fetch_history(ticker=ticker_input if ticker_input else None, model=model_filter, limit=50)
    
    if history is not None:
        if not history:
            st.info("No prediction history found for this period.")
            return

        # Display History List
        for item in history:
            timestamp = datetime.fromisoformat(item['created_at'])
            with st.expander(f"{item['ticker']} - {timestamp.strftime('%Y-%m-%d %H:%M')} ({item['model_type']})"):
                # Quick Metrics
                # Quick Metrics
                data = item.get('prediction_data')
                
                if not data:
                    st.warning("⏳ Prediction in progress...")
                else:
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
    # Fetch latest user info
    user_info = api_client.get_user_info()
    credits = user_info.get("credits", 0) if user_info else 0
    st.session_state.credits = credits

    st.title(f"Analysis for {st.session_state.get('last_ticker', 'Stock')}")
    
    st.sidebar.title("📈 Controls")
    
    # Credit Display
    st.sidebar.markdown(f"### 💎 Credits: {credits}")
    if st.sidebar.button("Buy Credits"):
        st.session_state.show_buy_credits = not st.session_state.get("show_buy_credits", False)
    
    if st.session_state.get("show_buy_credits", False):
        st.markdown("---")
        st.markdown("## 💎 Purchase Credits")
        st.info("Rate: 1 Credit = ₹10. Secure payment via Razorpay.")
        
        p1, p2, p3 = st.columns(3)
        
        with p1:
            st.markdown("### Starter")
            st.markdown("## ₹100")
            st.caption("10 Credits")
            if st.button("Buy Starter", key="pkg_10"):
               with st.spinner("Creating Order..."):
                   order = api_client.create_order(10)
                   if order:
                       components.render_razorpay_checkout(order)

        with p2:
            st.markdown("### Pro")
            st.markdown("## ₹500")
            st.caption("50 Credits")
            if st.button("Buy Pro", key="pkg_50"):
                with st.spinner("Creating Order..."):
                   order = api_client.create_order(50)
                   if order:
                       components.render_razorpay_checkout(order)

        with p3:
            st.markdown("### Whale")
            st.markdown("## ₹1000")
            st.caption("100 Credits")
            if st.button("Buy Whale", key="pkg_100"):
                with st.spinner("Creating Order..."):
                   order = api_client.create_order(100)
                   if order:
                       components.render_razorpay_checkout(order)
        st.markdown("---")

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
        if not components.is_valid_ticker(ticker):
             st.sidebar.error("⚠️ Invalid ticker format. Only letters, numbers, '.', and '-' are allowed.")
        else:
            # Save last ticker for title
            st.session_state.last_ticker = ticker
            
            result = api_client.get_prediction(ticker, lookback, model_map[model_choice])
            
            if result and result.get("error") == "INSUFFICIENT_CREDITS":
                cost = 3 if model_choice == "Additive Attention" else 2
                st.error(f"⚠️ Insufficient Credits! This model requires {cost} credits.")
                st.info("Opening purchase menu...")
                st.session_state.show_buy_credits = True
                st.rerun()
            elif result:
                components.visualize_prediction(result)
