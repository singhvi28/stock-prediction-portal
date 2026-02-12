import streamlit as st
import plotly.graph_objects as go
import streamlit.components.v1 as components

def render_razorpay_checkout(order_data):
    html_code = f"""
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <button id="rzp-button1" style="display:none;">Pay</button>
    <script>
    var options = {{
        "key": "{order_data['key_id']}",
        "amount": "{order_data['amount']}", 
        "currency": "{order_data['currency']}",
        "name": "{order_data['name']}",
        "description": "{order_data['description']}",
        "order_id": "{order_data['order_id']}", 
        "handler": function (response){{
            // Alert user and reload to reflect credits (webhook processing delay might apply)
            alert("Payment Successful! Payment ID: " + response.razorpay_payment_id + ". Please refresh the page in a few seconds to see updated credits.");
        }},
        "theme": {{
            "color": "#0e1117"
        }}
    }};
    var rzp1 = new Razorpay(options);
    rzp1.on('payment.failed', function (response){{
        alert("Payment Failed: " + response.error.description);
    }});
    // Auto open
    rzp1.open();
    </script>
    """
    components.html(html_code, height=450)

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

def visualize_prediction(result, show_metrics=True):
    st.markdown(f"### Historical Analysis: {result['ticker']}")

    # Display Metrics if available and requested
    if show_metrics and 'metrics' in result:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("RMSE", f"${result['metrics']['rmse']:.2f}")
        m2.metric("MAE", f"${result['metrics']['mae']:.2f}")
        m3.metric("MAPE", f"{result['metrics']['mape']:.2f}%")
        m4.metric("Directional Accuracy", f"{result['metrics']['directional_accuracy']:.2f}%")
    
    historical_dates = result.get('historical_dates', [])
    historical_prices = result.get('historical_prices', [])
    model_historical_predictions = result.get('model_historical_predictions', [])
    forecast_dates = result.get('forecast_dates', [])
    forecast_prices = result.get('forecast_prices', [])
    
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
    if historical_dates and model_historical_predictions and forecast_dates and forecast_prices:
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
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title="Price ($)"),
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

def is_valid_ticker(ticker):
    """
    Validates that the ticker contains only alphanumeric characters, dots, and hyphens.
    Returns True if valid or empty.
    Returns False if invalid characters are found.
    """
    if not ticker:
        return True
    return all(c.isalnum() or c in "-." for c in ticker)
