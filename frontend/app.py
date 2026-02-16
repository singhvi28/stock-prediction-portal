import streamlit as st
import api_client
from components import render_footer
from views import render_auth_page, show_history_page, render_dashboard

# Configuration
st.set_page_config(page_title="Stock Prediction Dashboard", layout="wide")

# Session State Initialization
if "token" not in st.session_state:
    st.session_state.token = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Check for reset token in URL (special flow)
query_params = st.query_params
reset_token = query_params.get("token")

# Token Persistence Logic
# If we have a token in URL but no session (refresh scenario), try to restore session
if not st.session_state.authenticated and "token" in query_params:
    token = query_params["token"]
    
    user_info = api_client.get_user_info(token)
    if user_info:
        st.session_state.token = token
        st.session_state.authenticated = True
    else:
        pass

# Determine if we are in reset flow
is_reset_flow = False
if not st.session_state.authenticated and reset_token:
    pass

if reset_token and not st.session_state.authenticated:
    pass

if reset_token and not st.session_state.authenticated:
     st.title("🔐 Reset Password")
     with st.form("reset_form"):
        new_p1 = st.text_input("New Password", type="password")
        new_p2 = st.text_input("Confirm Password", type="password")
        submit_reset = st.form_submit_button("Update Password")
        
        if submit_reset:
            if new_p1 != new_p2:
                st.error("Passwords do not match")
            else:
                success, msg = api_client.reset_password(reset_token, new_p1)
                if success:
                    st.success(msg)
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.error(msg) 
elif not st.session_state.authenticated:
    render_auth_page()
else:
    # Sidebar Navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "History"])
    
    if page == "Dashboard":
        render_dashboard()            
    elif page == "History":
        show_history_page()

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.token = None
        st.session_state.authenticated = False
        st.query_params.clear()
        st.rerun()
    
    render_footer()