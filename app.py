import streamlit as st
import pandas as pd
import requests

# Set page title
st.set_page_config(page_title="Crypto Market Risk Dashboard", layout="wide")
st.title("Crypto Market Risk Dashboard")
st.markdown("---")

# --- Data Fetching Functions ---
# Note: Use your actual CoinGecko API key here.
@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_global_market_data():
    """Fetches historical total crypto market cap data."""
    try:
        url = "https://api.coingecko.com/api/v3/global/market_cap_chart?days=90"
        headers = {"x-cg-demo-api-key": "YOUR_API_KEY"} # Use your API key
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data['market_cap_chart']['market_cap'], columns=['timestamp', 'market_cap'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
        df.set_index('timestamp', inplace=True)
        return df['market_cap']
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching global market data: {e}. Please check your API key.")
        return None

@st.cache_data(ttl=3600)
def fetch_coin_market_data(coin_id):
    """Fetches historical market cap for a specific coin."""
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=90"
        headers = {"x-cg-demo-api-key": "YOUR_API_KEY"} # Use your API key
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data['market_caps'], columns=['timestamp', 'market_cap'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
        df.set_index('timestamp', inplace=True)
        return df['market_cap']
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching {coin_id} data: {e}")
        return None

# --- Main App Logic ---
# Get all necessary data
total_market_cap = fetch_global_market_data()
btc_market_cap = fetch_coin_market_data('bitcoin')
eth_market_cap = fetch_coin_market_data('ethereum')

# Check if data fetching was successful
if total_market_cap is None or btc_market_cap is None or eth_market_cap is None:
    st.stop()

# Combine data into a single DataFrame for calculations
df = pd.DataFrame({
    'TOTAL': total_market_cap,
    'BTC': btc_market_cap,
    'ETH': eth_market_cap
}).dropna()

# Calculate TOTAL2 and OTHERS
df['TOTAL2'] = df['TOTAL'] - df['BTC']
df['OTHERS'] = df['TOTAL2'] - df['ETH']

# --- Calculate and Display Indicators ---

# 1. TOTAL Market Cap (TOTAL) vs. its SMAs
st.subheader("1. Total Crypto Market Cap")
df['SMA_10_TOTAL'] = df['TOTAL'].rolling(window=10).mean()
df['SMA_30_TOTAL'] = df['TOTAL'].rolling(window=30).mean()
latest_total = df.iloc[-1]
total_trend = "Bullish" if latest_total['SMA_10_TOTAL'] > latest_total['SMA_30_TOTAL'] else "Bearish"
st.metric(label="Market Cap Trend", value=total_trend, delta="10-day SMA vs 30-day SMA")

st.line_chart(df[['TOTAL', 'SMA_10_TOTAL', 'SMA_30_TOTAL']].tail(90))
st.markdown("---")


# 2. Total2/Total Ratio (Altcoins vs. BTC)
st.subheader("2. Altcoin Performance vs. Bitcoin (TOTAL2 / TOTAL)")
df['TOTAL2_DIV_TOTAL'] = (df['TOTAL2'] / df['TOTAL']) * 100
df['SMA_10_T2T'] = df['TOTAL2_DIV_TOTAL'].rolling(window=10).mean()
df['SMA_30_T2T'] = df['TOTAL2_DIV_TOTAL'].rolling(window=30).mean()

latest_t2t = df.iloc[-1]
t2t_trend = "Altcoins Outperforming" if latest_t2t['SMA_10_T2T'] > latest_t2t['SMA_30_T2T'] else "Bitcoin Outperforming"
st.metric(label="Altcoin Dominance Trend", value=t2t_trend, delta="10-day SMA vs 30-day SMA")
st.line_chart(df[['TOTAL2_DIV_TOTAL', 'SMA_10_T2T', 'SMA_30_T2T']].tail(90))
st.caption("This chart shows the percentage of the total market cap that is made up of altcoins (excluding Bitcoin). An uptrend indicates altcoins are gaining market share relative to Bitcoin.")
st.markdown("---")


# 3. OTHERS/TOTAL2 Ratio (High-Risk Alts vs. Main Alts)
st.subheader("3. High-Risk Altcoin Performance (OTHERS / TOTAL2)")
df['OTHERS_DIV_TOTAL2'] = (df['OTHERS'] / df['TOTAL2']) * 100
df['SMA_10_OT2'] = df['OTHERS_DIV_TOTAL2'].rolling(window=10).mean()
df['SMA_30_OT2'] = df['OTHERS_DIV_TOTAL2'].rolling(window=30).mean()

latest_ot2 = df.iloc[-1]
ot2_trend = "High-Risk Alts Outperforming" if latest_ot2['SMA_10_OT2'] > latest_ot2['SMA_30_OT2'] else "Main Alts Outperforming"
st.metric(label="High-Risk Altcoin Trend", value=ot2_trend, delta="10-day SMA vs 30-day SMA")
st.line_chart(df[['OTHERS_DIV_TOTAL2', 'SMA_10_OT2', 'SMA_30_OT2']].tail(90))
st.caption("This chart shows the percentage of the altcoin market cap that is made up of smaller, higher-risk altcoins (excluding Bitcoin and Ethereum). An uptrend indicates a speculative, 'risk-on' environment.")
st.markdown("---")

st.info("Disclaimer: This tool is for informational purposes only and should not be considered financial advice. Market indicators can be volatile.")
