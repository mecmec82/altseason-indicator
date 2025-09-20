import streamlit as st
import pandas as pd
import requests
import time

# Set Streamlit page configuration
st.set_page_config(
    page_title="Crypto Market Risk Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Constants & Configuration ---
COINGECKO_API_KEY = "CG-g2VJdQPBZKnue923aTbM4b1h" # ⚠️ Replace with your actual key
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
HEADERS = {"x-cg-demo-api-key": COINGECKO_API_KEY}

# Top 10 coins by CoinGecko ranking as of late 2025.
# This list needs to be updated periodically for accuracy.
TOP_10_COINS = [
    'bitcoin',
    'ethereum',
    'solana',
    'xrp',
    'bnb',
    'cardano',
    'dogecoin',
    'shiba-inu',
    'polkadot',
    'chainlink'
]

# --- Helper Functions ---
@st.cache_data(ttl=3600)
def fetch_global_market_data():
    """Fetches historical total crypto market cap data."""
    try:
        url = f"{COINGECKO_BASE_URL}/global/market_cap_chart?days=90"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data['market_caps'], columns=['timestamp', 'market_cap'])
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
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart?vs_currency=usd&days=90"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data['market_caps'], columns=['timestamp', 'market_cap'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
        df.set_index('timestamp', inplace=True)
        return df['market_cap']
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data for {coin_id}: {e}")
        return None

def calculate_sma_and_trend(series, window_short=10, window_long=30):
    """Calculates SMAs and determines the latest trend."""
    sma_short = series.rolling(window=window_short).mean()
    sma_long = series.rolling(window=window_long).mean()
    
    latest_short = sma_short.iloc[-1]
    latest_long = sma_long.iloc[-1]
    
    trend = "Bullish" if latest_short > latest_long else "Bearish"
    
    return sma_short, sma_long, trend

def plot_indicator(df, title, data_col, sma_short_col, sma_long_col, trend):
    """Generates and displays a line chart for an indicator."""
    st.subheader(title)
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.metric(label="Trend", value=trend)
    
    with col2:
        st.line_chart(df[[data_col, sma_short_col, sma_long_col]].tail(90))

# --- Main Streamlit App Layout ---
st.title("Crypto Market Risk Dashboard 📊")
st.markdown("""
Welcome to the Crypto Market Risk Dashboard. This tool helps you assess market sentiment by analyzing key moving averages for three crucial indicators:
* **Total Market Cap:** The overall health of the crypto market.
* **TOTAL2 / TOTAL:** Shows if altcoins are outperforming Bitcoin.
* **OTHERS / TOTAL:** Shows if smaller, high-risk altcoins are outperforming the overall market.
""")

st.markdown("---")

# Data fetching and combining
with st.spinner('Fetching market data... This may take a moment due to API call limits.'):
    total_market_cap = fetch_global_market_data()
    
    # Check if global market data is available
    if total_market_cap is None or total_market_cap.empty:
        st.error("Could not retrieve global market data. The app cannot proceed.")
        st.stop()

    # Fetch data for top 10 coins
    top_10_market_caps = {}
    for coin in TOP_10_COINS:
        market_cap_series = fetch_coin_market_data(coin)
        if market_cap_series is not None:
            top_10_market_caps[coin] = market_cap_series
        # Sleep to respect CoinGecko's free API rate limit (30 calls/minute)
        time.sleep(2) 

# Combine all data into a single DataFrame
df = pd.DataFrame({'TOTAL': total_market_cap}).dropna()
df_top_10 = pd.DataFrame(top_10_market_caps).dropna()

# Align indices and merge
df = df.reindex(df_top_10.index, method='pad')
df['SUM_TOP_10'] = df_top_10.sum(axis=1)

# Ensure the combined DataFrame is ready for analysis
df = df.dropna()

if not df.empty:
    
    ## 1. TOTAL Market Cap (TOTAL) vs. SMAs
    st.header("1. Total Crypto Market Cap")
    st.write("Measures the health of the entire crypto market. When the short-term SMA crosses above the long-term SMA, it's a bullish signal.")
    
    sma_10_total, sma_30_total, total_trend = calculate_sma_and_trend(df['TOTAL'])
    df['SMA_10_TOTAL'] = sma_10_total
    df['SMA_30_TOTAL'] = sma_30_total
    
    plot_indicator(df, "Total Market Cap with SMAs", 'TOTAL', 'SMA_10_TOTAL', 'SMA_30_TOTAL', total_trend)
    st.markdown("---")

    ## 2. TOTAL2/TOTAL Ratio (Altcoins vs. BTC)
    st.header("2. Altcoin Performance (TOTAL2 / TOTAL)")
    st.write("This ratio tracks the market share of all altcoins combined (excluding Bitcoin) relative to the total market. A rising trend suggests altcoins are gaining market share, a potential precursor to an 'altseason'.")
    
    df['TOTAL2'] = df['TOTAL'] - df['SUM_TOP_10'] + df['bitcoin']
    df['TOTAL2_DIV_TOTAL'] = (df['TOTAL2'] / df['TOTAL']) * 100
    
    sma_10_t2t, sma_30_t2t, t2t_trend = calculate_sma_and_trend(df['TOTAL2_DIV_TOTAL'])
    df['SMA_10_T2T'] = sma_10_t2t
    df['SMA_30_T2T'] = sma_30_t2t
    
    plot_indicator(df, "TOTAL2 / TOTAL Ratio", 'TOTAL2_DIV_TOTAL', 'SMA_10_T2T', 'SMA_30_T2T', t2t_trend)
    st.markdown("---")
    
    ## 3. OTHERS/TOTAL Ratio (High-Risk Assets)
    st.header("3. High-Risk Altcoin Performance (OTHERS / TOTAL)")
    st.write("This is a key indicator for 'altseason'. It measures the market share of all cryptocurrencies **excluding the top 10**. An uptrend shows capital flowing into highly speculative, smaller-cap coins, indicating a 'risk-on' environment.")
    
    df['OTHERS'] = df['TOTAL'] - df['SUM_TOP_10']
    df['OTHERS_DIV_TOTAL'] = (df['OTHERS'] / df['TOTAL']) * 100
    
    sma_10_others, sma_30_others, others_trend = calculate_sma_and_trend(df['OTHERS_DIV_TOTAL'])
    df['SMA_10_OTHERS'] = sma_10_others
    df['SMA_30_OTHERS'] = sma_30_others
    
    plot_indicator(df, "OTHERS / TOTAL Ratio", 'OTHERS_DIV_TOTAL', 'SMA_10_OTHERS', 'SMA_30_OTHERS', others_trend)
    st.markdown("---")

else:
    st.error("Failed to generate indicators due to data fetching issues. Please check your API key and try again.")

st.info("Disclaimer: This tool is for informational purposes only and is not financial advice. All data is sourced from a free API, which may have limitations on historical data and real-time updates. The list of top 10 coins is manually maintained and may not be up-to-the-minute accurate.")
