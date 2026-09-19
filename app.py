import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

ASSETS = {
    "gold": {"name": "Gold", "ticker": "GC=F"},
    "bitcoin": {"name": "Bitcoin", "ticker": "BTC-USD"},
    "nvidia": {"name": "NVIDIA", "ticker": "NVDA"},
}

STRATEGIES = {
    "sma": "SMA Crossover",
    "ema": "EMA Trend",
    "momentum": "Momentum",
    "mean_reversion": "Mean Reversion",
}


def load_data(asset="nvidia", period="5y"):
    ticker = ASSETS.get(asset, ASSETS["nvidia"])["ticker"]
    data = yf.download(ticker, period=period, auto_adjust=True, progress=False)

    if data.empty:
        raise ValueError("Market data could not be loaded right now.")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data[["Open", "High", "Low", "Close", "Volume"]].dropna()
    data.index = pd.to_datetime(data.index)
    return data


def metrics(data):
    close = data["Close"]
    returns = close.pct_change().dropna()

    total_return = (close.iloc[-1] / close.iloc[0] - 1) * 100
    annual_return = (1 + returns.mean()) ** 252 - 1
    volatility = returns.std() * np.sqrt(252)
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() else 0

    running_max = close.cummax()
    drawdown = close / running_max - 1
    max_drawdown = drawdown.min() * 100

    return {
        "total_return": round(float(total_return), 2),
        "annual_return": round(float(annual_return * 100), 2),
        "volatility": round(float(volatility * 100), 2),
        "sharpe": round(float(sharpe), 2),
        "max_drawdown": round(float(max_drawdown), 2),
    }


def add_indicators(data, fast=20, slow=50):
    df = data.copy()
    df["SMA Fast"] = df["Close"].rolling(fast).mean()
    df["SMA Slow"] = df["Close"].rolling(slow).mean()
    df["EMA Fast"] = df["Close"].ewm(span=fast, adjust=False).mean()
    df["EMA Slow"] = df["Close"].ewm(span=slow, adjust=False).mean()
    df["Daily Return"] = df["Close"].pct_change()
    df["Rolling Volatility"] = df["Daily Return"].rolling(30).std() * np.sqrt(252)
    df["Cumulative Return"] = (1 + df["Daily Return"].fillna(0)).cumprod() - 1
    return df


def backtest(data, strategy, initial_capital=100000, transaction_cost=0.001, fast=20, slow=50):
    df = add_indicators(data, fast, slow)
    close = df["Close"]

    if strategy == "sma":
        signal = (df["SMA Fast"] > df["SMA Slow"]).astype(int)
    elif strategy == "ema":
        signal = (df["EMA Fast"] > df["EMA Slow"]).astype(int)
    elif strategy == "momentum":
        signal = (close > close.shift(20)).astype(int)
    else:
        mean = close.rolling(20).mean()
        signal = (close < mean * 0.97).astype(int)

    signal = signal.fillna(0)
    position_change = signal.diff().abs().fillna(signal.abs())
    asset_return = close.pct_change().fillna(0)

    strategy_return = signal.shift(1).fillna(0) * asset_return
    strategy_return -= position_change * transaction_cost

    equity = initial_capital * (1 + strategy_return).cumprod()
    benchmark = initial_capital * (1 + asset_return).cumprod()

    result = df.copy()
    result["Signal"] = signal
    result["Strategy Return"] = strategy_return
    result["Equity"] = equity
    result["Benchmark"] = benchmark
    result["Drawdown"] = equity / equity.cummax() - 1

    r = strategy_return[strategy_return != 0]
    sharpe = (r.mean() / r.std()) * np.sqrt(252) if len(r) > 1 and r.std() else 0
    max_dd = result["Drawdown"].min() * 100
    total = (equity.iloc[-1] / initial_capital - 1) * 100
    trades = int((position_change > 0).sum())

    summary = {
        "final_value": round(float(equity.iloc[-1]), 2),
        "return": round(float(total), 2),
        "sharpe": round(float(sharpe), 2),
        "max_drawdown": round(float(max_dd), 2),
        "trades": trades,
        "benchmark_return": round(float((benchmark.iloc[-1] / initial_capital - 1) * 100), 2),
    }

    return result, summary


def clean_number(value):
    if pd.isna(value) or np.isinf(value):
        return None
    return round(float(value), 4)


@app.route("/")
def index():
    return render_template("index.html", assets=ASSETS, strategies=STRATEGIES)


@app.route("/api/analysis")
def analysis():
    asset = request.args.get("asset", "nvidia")
    period = request.args.get("period", "5y")
    fast = int(request.args.get("fast", 20))
    slow = int(request.args.get("slow", 50))

    data = add_indicators(load_data(asset, period), fast, slow)
    m = metrics(data)

    recent = data.tail(365).copy()
    chart = []
    for idx, row in recent.iterrows():
        chart.append({
            "date": idx.strftime("%Y-%m-%d"),
            "close": clean_number(row["Close"]),
            "sma_fast": clean_number(row["SMA Fast"]),
            "sma_slow": clean_number(row["SMA Slow"]),
            "ema_fast": clean_number(row["EMA Fast"]),
            "ema_slow": clean_number(row["EMA Slow"]),
            "return": clean_number(row["Daily Return"] * 100),
            "volatility": clean_number(row["Rolling Volatility"] * 100),
            "drawdown": clean_number((row["Close"] / data["Close"].cummax().loc[idx] - 1) * 100),
        })

    return jsonify({
        "asset": ASSETS[asset]["name"],
        "metrics": m,
        "chart": chart,
        "last_price": clean_number(data["Close"].iloc[-1]),
        "last_date": data.index[-1].strftime("%Y-%m-%d"),
    })


@app.route("/api/backtest", methods=["GET"])
def run_backtest():
    asset = request.args.get("asset", "nvidia")
    strategy = request.args.get("strategy", "sma")
    period = request.args.get("period", "5y")
    capital = float(request.args.get("capital", 100000))
    cost = float(request.args.get("cost", 0.001))
    fast = int(request.args.get("fast", 20))
    slow = int(request.args.get("slow", 50))

    data = load_data(asset, period)
    result, summary = backtest(data, strategy, capital, cost, fast, slow)

    recent = result.tail(365)
    chart = []
    for idx, row in recent.iterrows():
        chart.append({
            "date": idx.strftime("%Y-%m-%d"),
            "equity": clean_number(row["Equity"]),
            "benchmark": clean_number(row["Benchmark"]),
            "drawdown": clean_number(row["Drawdown"] * 100),
            "signal": int(row["Signal"]),
        })

    return jsonify({
        "asset": ASSETS[asset]["name"],
        "strategy": STRATEGIES[strategy],
        "summary": summary,
        "chart": chart,
    })


@app.route("/api/correlation")
def correlation():
    period = request.args.get("period", "5y")
    series = {}

    for key, info in ASSETS.items():
        df = load_data(key, period)
        series[info["name"]] = df["Close"].pct_change()

    returns = pd.DataFrame(series).dropna()
    corr = returns.corr()

    matrix = {
        row: {col: round(float(corr.loc[row, col]), 3) for col in corr.columns}
        for row in corr.index
    }

    rolling = returns["Bitcoin"].rolling(60).corr(returns["NVIDIA"]).dropna().tail(365)
    rolling_data = [
        {"date": idx.strftime("%Y-%m-%d"), "value": round(float(value), 4)}
        for idx, value in rolling.items()
    ]

    return jsonify({"matrix": matrix, "rolling_btc_nvidia": rolling_data})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
