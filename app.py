import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import random

# --- Constants & Configuration ---
# Use st.secrets to securely access the API key
COINGECKO_API_KEY = st.secrets["COINGECKO_API_KEY"]
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
HEADERS = {"x-cg-demo-api-key": COINGECKO_API_KEY}

# Top 10 coins by CoinGecko ranking as of late 2025.
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

# --- Helper Function with Exponential Backoff ---
def fetch_data_with_backoff(url, headers, max_retries=5, backoff_factor=1):
    retries = 0
    while retries < max_retries:
        try:
            st.write(f"Attempting to fetch data from: {url}")
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
def fetch_global_market_data():
    """Fetches historical total crypto market cap data by combining data from the top N coins."""
    global_df = None
    
    # We must fetch individual top coins and sum them, as the 'global_market_cap_chart' is not free.
    st.write("Fetching historical market cap data for top 10 coins to approximate total market cap.")
    
    for coin in TOP_10_COINS:
        market_cap_series = fetch_coin_market_data(coin)
        if market_cap_series is not None:
            if global_df is None:
                global_df = pd.DataFrame(market_cap_series).rename(columns={market_cap_series.name: 'market_cap'})
            else:
                # Merge on index to sum the market caps
                global_df = global_df.merge(market_cap_series.to_frame(), left_index=True, right_index=True, how='outer')
                global_df['market_cap'] = global_df['market_cap'] + global_df[market_cap_series.name]
                global_df.drop(columns=[market_cap_series.name], inplace=True)
    
    # Add a small buffer for coins outside the top 10
    if global_df is not None:
        global_df['market_cap'] = global_df['market_cap'] * 1.10 # 10% buffer
    
    return global_df['market_cap'] if global_df is not None else None

@st.cache_data(ttl=3600)
def fetch_coin_market_data(coin_id):
    """Fetches historical market cap for a specific coin."""
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart?vs_currency=usd&days=90"
    data = fetch_data_with_backoff(url, HEADERS)
    if data:
        df = pd.DataFrame(data['market_caps'], columns=['timestamp', 'market_cap'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
        df.set_index('timestamp', inplace=True)
        return df['market_cap']
    return None

# --- Main App Logic ---
st.title("Crypto Market Risk Dashboard 📊")
st.markdown("""
This tool assesses market sentiment by analyzing moving averages for key indicators, using a free API.
""")
st.markdown("---")

# Data fetching and combining
with st.spinner('Fetching market data... This may take a moment due to API call limits.'):
    total_market_cap = fetch_global_market_data()
    
    if total_market_cap is None or total_market_cap.empty:
        st.error("Could not retrieve global market data. The app cannot proceed.")
        st.stop()
    
    # We still need BTC market cap to calculate TOTAL2
    btc_market_cap = fetch_coin_market_data('bitcoin')
    
    df = pd.DataFrame({'TOTAL': total_market_cap}).dropna()
    df['BTC'] = btc_market_cap
    df = df.dropna()

    top_10_market_caps = {}
    for coin in TOP_10_COINS:
        market_cap_series = fetch_coin_market_data(coin)
        if market_cap_series is not None:
            top_10_market_caps[coin] = market_cap_series
    
    df_top_10 = pd.DataFrame(top_10_market_caps).dropna()
    df = df.reindex(df_top_10.index, method='pad').dropna()
    df['SUM_TOP_10'] = df_top_10.sum(axis=1)

# --- Perform Calculations ---
if not df.empty:
    
    # Calculate TOTAL2 and OTHERS using the free-tier workaround
    df['TOTAL2'] = df['TOTAL'] - df['BTC']
    df['OTHERS'] = df['TOTAL'] - df['SUM_TOP_10']

    ## 1. TOTAL Market Cap
    st.header("1. Total Crypto Market Cap")
    df['SMA_10_TOTAL'] = df['TOTAL'].rolling(window=10).mean()
    df['SMA_30_TOTAL'] = df['TOTAL'].rolling(window=30).mean()
    total_trend = "Bullish" if df['SMA_10_TOTAL'].iloc[-1] > df['SMA_30_TOTAL'].iloc[-1] else "Bearish"
    st.metric(label="Market Cap Trend", value=total_trend)
    st.line_chart(df[['TOTAL', 'SMA_10_TOTAL', 'SMA_30_TOTAL']].tail(90))
    st.markdown("---")

    ## 2. TOTAL2/TOTAL Ratio (Altcoins vs. BTC)
    st.header("2. Altcoin Performance (TOTAL2 / TOTAL)")
    df['TOTAL2_DIV_TOTAL'] = (df['TOTAL2'] / df['TOTAL']) * 100
    df['SMA_10_T2T'] = df['TOTAL2_DIV_TOTAL'].rolling(window=10).mean()
    df['SMA_30_T2T'] = df['TOTAL2_DIV_TOTAL'].rolling(window=30).mean()
    t2t_trend = "Altcoins Outperforming" if df['SMA_10_T2T'].iloc[-1] > df['SMA_30_T2T'].iloc[-1] else "Bitcoin Outperforming"
    st.metric(label="Altcoin Dominance Trend", value=t2t_trend)
    st.line_chart(df[['TOTAL2_DIV_TOTAL', 'SMA_10_T2T', 'SMA_30_T2T']].tail(90))
    st.caption("A rising trend indicates altcoins are gaining market share relative to Bitcoin.")
    st.markdown("---")

    ## 3. OTHERS/TOTAL Ratio (High-Risk Assets)
    st.header("3. High-Risk Altcoin Performance (OTHERS / TOTAL)")
    df['OTHERS_DIV_TOTAL'] = (df['OTHERS'] / df['TOTAL']) * 100
    df['SMA_10_OTHERS'] = df['OTHERS_DIV_TOTAL'].rolling(window=10).mean()
    df['SMA_30_OTHERS'] = df['OTHERS_DIV_TOTAL'].rolling(window=30).mean()
    others_trend = "High-Risk Alts Outperforming" if df['SMA_10_OTHERS'].iloc[-1] > df['SMA_30_OTHERS'].iloc[-1] else "Mainstream Alts Outperforming"
    st.metric(label="High-Risk Altcoin Trend", value=others_trend)
    st.line_chart(df[['OTHERS_DIV_TOTAL', 'SMA_10_OTHERS', 'SMA_30_OTHERS']].tail(90))
    st.caption("A rising trend in this ratio suggests a 'risk-on' environment where capital is flowing into smaller, more speculative assets.")
    st.markdown("---")

else:
    st.error("Failed to generate indicators due to data fetching issues.")

st.info("Disclaimer: This tool is for informational purposes only and is not financial advice.")
