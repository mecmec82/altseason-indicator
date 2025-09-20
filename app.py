import streamlit as st
import pandas as pd
import requests

# Set page title and a brief description
st.title("Crypto Market Cap Direction Indicator")
st.write("This app analyzes the total crypto market cap to show if the 10-day Simple Moving Average (SMA) is above the 30-day SMA, indicating a potential bullish trend.")

# --- Data Fetching Function ---
# Note: Replace 'YOUR_API_KEY' with your actual API key from CoinGecko or CoinMarketCap.
# This example uses a placeholder API call structure. You'll need to adapt it to the specific API's documentation.
@st.cache_data(ttl=3600)  # Cache data for 1 hour to avoid excessive API calls
def get_crypto_market_cap_data():
    """
    Fetches historical total crypto market cap data from a free API.
    """
    try:
        # Example CoinGecko API endpoint for Bitcoin market cap
        # You'll need to find the specific endpoint for the *total* market cap
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=90"
        headers = {"x-cg-demo-api-key": "CG-g2VJdQPBZKnue923aTbM4b1h"} # CoinGecko uses this header for free tier
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        
        data = response.json()
        market_caps = data["market_caps"]
        
        df = pd.DataFrame(market_caps, columns=['timestamp', 'market_cap'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {e}. Please check your API key and network connection.")
        return None

# --- Main App Logic ---
df = get_crypto_market_cap_data()

if df is not None:
    # Calculate SMAs
    df['SMA_10'] = df['market_cap'].rolling(window=10).mean()
    df['SMA_30'] = df['market_cap'].rolling(window=30).mean()

    # Determine market direction
    latest_data = df.dropna().iloc[-1]
    is_bullish = latest_data['SMA_10'] > latest_data['SMA_30']

    # Display results
    st.subheader("Market Direction")
    if is_bullish:
        st.metric(label="Market Direction", value="Bullish", delta="10-day SMA > 30-day SMA")
        st.success("The 10-day SMA is above the 30-day SMA. This can indicate a potential uptrend. 📈")
    else:
        st.metric(label="Market Direction", value="Bearish", delta="10-day SMA ≤ 30-day SMA")
        st.warning("The 10-day SMA is not above the 30-day SMA. This can indicate a potential downtrend. 📉")
    
    st.markdown("---")
    
    # Plotting the data
    st.subheader("Total Crypto Market Cap with SMAs")
    st.line_chart(df[['market_cap', 'SMA_10', 'SMA_30']].tail(60))

    st.caption("Data provided by a free cryptocurrency API. The SMA values are a simplified indicator and should not be used as financial advice. ")
