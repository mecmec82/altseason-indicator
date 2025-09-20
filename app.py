import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import random

# --- Constants & Configuration ---
COINGECKO_API_KEY = st.secrets["COINGECKO_API_KEY"]
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
HEADERS = {"x-cg-demo-api-key": COINGECKO_API_KEY}

# Corrected Top 10 coins by CoinGecko ranking as of late 2025.
TOP_10_COINS = [
    'bitcoin',
    'ethereum',
    'solana',
    'ripple',
    'binancecoin',
    'cardano',
    'dogecoin',
    'shiba-inu',
    'polkadot',
    'chainlink'
]

# --- Helper Function with Exponential Backoff ---
def fetch_data_with_backoff(url, headers, max_retries=5, backoff_factor=1):
    """
    Fetches data from a URL with exponential backoff and jitter for rate-limiting.
    """
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if response.status_code == 429:
                delay = (backoff_factor * (2 ** retries)) + random.uniform(0, 1)
                st.warning(f"Rate limit hit. Retrying in {delay:.2f} seconds... (Attempt {retries + 1}/{max_retries})")
                time.sleep(delay)
                retries += 1
            else:
                st.error(f"Error fetching data from {url}: {e}")
                return None
    st.error("Max retries exceeded. Could not fetch data.")
    return None

# --- Data Fetching Functions ---
@st.cache_data(ttl=3600)
def fetch_coin_market_data(coin_id):
    """Fetches historical market cap for a specific coin."""
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart?vs_currency=usd&days=90"
    data = fetch_data_with_backoff(url, HEADERS)
    if data:
        df = pd.DataFrame(data['market_caps'], columns=['timestamp', 'market_cap'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
        df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
        df.set_index('timestamp', inplace=True)
        return df['market_cap'].rename(coin_id)
    return None

@st.cache_data(ttl=3600)
def fetch_aggregated_total_market_cap():
    """
    Aggregates market cap from individual top coins to approximate total market cap.
    """
    all_coin_market_caps = {}
    for coin_id in TOP_10_COINS:
        market_cap_series = fetch_coin_market_data(coin_id)
        if market_cap_series is not None and not market_cap_series.empty:
            all_coin_market_caps[coin_id] = market_cap_series
        time.sleep(0.5)

    if not all_coin_market_caps:
        st.error("Could not fetch market data for any of the top coins.")
        return None

    combined_df = pd.DataFrame(all_coin_market_caps)
    combined_df = combined_df.dropna()

    if combined_df.empty:
        st.error("Combined market cap data is empty after dropping NaNs.")
        return None

    total_market_cap_series = combined_df.sum(axis=1) * 1.10
    total_market_cap_series.name = 'TOTAL'
    return total_market_cap_series

# --- Main App Layout ---
st.set_page_config(
    page_title="Crypto Market Risk Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.title("Crypto Market Risk Dashboard 📊")

# Data fetching and combining
with st.spinner('Fetching market data... This may take a moment due to API call limits. Please be patient.'):
    total_market_cap = fetch_aggregated_total_market_cap()
    
    if total_market_cap is None or total_market_cap.empty:
        st.error("Could not retrieve enough market data to proceed. Please check your internet connection or CoinGecko API key.")
        st.stop()
    
    individual_coin_market_caps = {}
    for coin_id in TOP_10_COINS:
        market_cap_series = fetch_coin_market_data(coin_id)
        if market_cap_series is not None and not market_cap_series.empty:
            individual_coin_market_caps[coin_id] = market_cap_series
        time.sleep(0.5)

    if not individual_coin_market_caps:
        st.error("Could not fetch individual coin market data for calculations. The app cannot proceed.")
        st.stop()

    df = pd.DataFrame({'TOTAL': total_market_cap})
    
    for coin_id, series in individual_coin_market_caps.items():
        df = df.merge(series.to_frame(), left_index=True, right_index=True, how='left')

    df = df.dropna()

    missing_top_coins = [coin for coin in TOP_10_COINS if coin not in df.columns]
    if missing_top_coins:
        df['SUM_TOP_10'] = df[[col for col in TOP_10_COINS if col in df.columns]].sum(axis=1)
    else:
        df['SUM_TOP_10'] = df[TOP_10_COINS].sum(axis=1)

# --- Perform Calculations and Present as Table ---
if not df.empty and 'bitcoin' in df.columns:
    df['TOTAL2'] = df['TOTAL'] - df['bitcoin']
    df['OTHERS'] = df['TOTAL'] - df['SUM_TOP_10']

    # Calculate SMAs for all indicators
    df['SMA_10_TOTAL'] = df['TOTAL'].rolling(window=10).mean()
    df['SMA_30_TOTAL'] = df['TOTAL'].rolling(window=30).mean()
    
    df['TOTAL2_DIV_TOTAL'] = (df['TOTAL2'] / df['TOTAL']) * 100
    df['SMA_10_T2T'] = df['TOTAL2_DIV_TOTAL'].rolling(window=10).mean()
    df['SMA_30_T2T'] = df['TOTAL2_DIV_TOTAL'].rolling(window=30).mean()

    df['OTHERS_DIV_TOTAL'] = (df['OTHERS'] / df['TOTAL']) * 100
    df['SMA_10_OTHERS'] = df['OTHERS_DIV_TOTAL'].rolling(window=10).mean()
    df['SMA_30_OTHERS'] = df['OTHERS_DIV_TOTAL'].rolling(window=30).mean()

    # Determine trend
    total_trend = "Bullish" if df['SMA_10_TOTAL'].iloc[-1] > df['SMA_30_TOTAL'].iloc[-1] else "Bearish"
    t2t_trend = "Bullish" if df['SMA_10_T2T'].iloc[-1] > df['SMA_30_T2T'].iloc[-1] else "Bearish"
    others_trend = "Bullish" if df['SMA_10_OTHERS'].iloc[-1] > df['SMA_30_OTHERS'].iloc[-1] else "Bearish"

    # Create the summary DataFrame
    summary_data = {
        'Indicator': [
            "Total Market Cap (TOTAL)", 
            "Altcoins vs. BTC (TOTAL2 / TOTAL)", 
            "High-Risk Alts (OTHERS / TOTAL)"
        ],
        'Trend': [
            total_trend, 
            t2t_trend, 
            others_trend
        ],
        'Description': [
            "A bullish trend indicates the overall crypto market is in a positive uptrend.",
            "A bullish trend indicates altcoins are outperforming Bitcoin, suggesting a 'risk-on' rotation from BTC into altcoins.",
            "A bullish trend indicates smaller, more speculative altcoins are outperforming the rest of the market, signaling high-risk appetite."
        ]
    }
    summary_df = pd.DataFrame(summary_data)

    st.markdown("### Current Market Sentiment Indicators")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.markdown("---")

else:
    st.error("Failed to generate indicators due to insufficient data or missing 'bitcoin' column.")

st.info("Disclaimer: This tool is for informational purposes only and is not financial advice. All data is sourced from a free API and may have limitations on historical data and real-time updates. The TOTAL market cap is approximated by summing the top 10 coins plus a buffer.")
