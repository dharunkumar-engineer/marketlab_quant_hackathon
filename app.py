import os
import time
import threading
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

from flask import Flask, jsonify, render_template, request


# ============================================================
# MARKETLAB
# Quantitative Multi-Asset Financial Intelligence Platform
# ============================================================

app = Flask(__name__)


# ============================================================
# ASSETS
# ============================================================

ASSETS = {
    "gold": {
        "name": "Gold",
        "ticker": "GC=F",
    },
    "bitcoin": {
        "name": "Bitcoin",
        "ticker": "BTC-USD",
    },
    "nvidia": {
        "name": "NVIDIA",
        "ticker": "NVDA",
    },
}


STRATEGIES = {
    "sma": "SMA Crossover",
    "ema": "EMA Trend",
    "momentum": "Momentum",
    "mean_reversion": "Mean Reversion",
}


# ============================================================
# CACHE
# ============================================================

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")

os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_SECONDS = 60 * 30  # 30 minutes

_data_cache = {}
_cache_lock = threading.Lock()


# ============================================================
# PERIOD CONVERSION
# ============================================================

PERIOD_MAP = {
    "1mo": "1mo",
    "3mo": "3mo",
    "6mo": "6mo",
    "1y": "1y",
    "2y": "2y",
    "5y": "5y",
    "10y": "10y",
    "max": "max",
}


# ============================================================
# HELPERS
# ============================================================

def clean_number(value):
    """
    Convert numpy/pandas numbers to JSON-safe numbers.
    """
    try:
        if value is None:
            return None

        value = float(value)

        if np.isnan(value) or np.isinf(value):
            return None

        return round(value, 6)

    except Exception:
        return None


def safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value, default):
    try:
        return float(value)
    except Exception:
        return default


def normalize_columns(data):
    """
    Normalize yfinance output so that Open/High/Low/Close/Volume
    are always simple columns.
    """

    if data is None or data.empty:
        return data

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    available = [
        column for column in required
        if column in data.columns
    ]

    if "Close" not in available:
        return pd.DataFrame()

    data = data[available].copy()

    for column in available:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    data = data.dropna(subset=["Close"])

    data.index = pd.to_datetime(data.index)

    if getattr(data.index, "tz", None) is not None:
        data.index = data.index.tz_localize(None)

    data = data.sort_index()

    return data


# ============================================================
# LOCAL CACHE FILE
# ============================================================

def cache_file(asset, period):
    safe_period = period.replace("/", "_")

    return os.path.join(
        CACHE_DIR,
        f"{asset}_{safe_period}.csv"
    )


def save_disk_cache(asset, period, data):
    """
    Save downloaded market data locally.

    Render's filesystem can be temporary, but this still prevents
    repeated downloads during the lifetime of the running service.
    """

    try:
        path = cache_file(asset, period)

        data.to_csv(path)

    except Exception as error:
        print(
            f"[CACHE] Could not save {asset}: {error}",
            flush=True
        )


def load_disk_cache(asset, period):
    """
    Load previously cached market data if available.
    """

    path = cache_file(asset, period)

    if not os.path.exists(path):
        return None

    try:
        modified = os.path.getmtime(path)

        age = time.time() - modified

        if age > CACHE_SECONDS:
            return None

        data = pd.read_csv(
            path,
            index_col=0,
            parse_dates=True
        )

        data = normalize_columns(data)

        if data.empty:
            return None

        return data

    except Exception as error:
        print(
            f"[CACHE] Could not read cache {asset}: {error}",
            flush=True
        )

        return None


# ============================================================
# MARKET DATA
# ============================================================

def download_market_data(asset, period):
    """
    Download historical market data.

    Important:
    - Only one download is attempted at a time.
    - Threads are disabled.
    - Yahoo errors are caught.
    - The Flask worker is not intentionally crashed.
    """

    if asset not in ASSETS:
        asset = "nvidia"

    period = PERIOD_MAP.get(period, "5y")

    ticker = ASSETS[asset]["ticker"]

    print(
        f"[DATA] Requesting {asset} ({ticker}) - {period}",
        flush=True
    )

    try:

        data = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
            group_by="column",
        )

        data = normalize_columns(data)

        if data.empty:
            raise ValueError(
                f"No market data returned for {ticker}"
            )

        save_disk_cache(
            asset,
            period,
            data
        )

        return data

    except Exception as error:

        print(
            f"[DATA ERROR] {ticker}: {repr(error)}",
            flush=True
        )

        raise RuntimeError(
            f"Market data provider is temporarily unavailable "
            f"for {ASSETS[asset]['name']}."
        )


def load_data(asset="nvidia", period="5y"):
    """
    Main market-data loader.

    Order:

    1. Memory cache
    2. Local disk cache
    3. Yahoo Finance
    4. Clear API error

    This prevents repeated Yahoo Finance requests.
    """

    if asset not in ASSETS:
        asset = "nvidia"

    period = PERIOD_MAP.get(period, "5y")

    cache_key = f"{asset}:{period}"

    # --------------------------------------------------------
    # MEMORY CACHE
    # --------------------------------------------------------

    with _cache_lock:

        cached = _data_cache.get(cache_key)

        if cached is not None:

            timestamp, data = cached

            if time.time() - timestamp < CACHE_SECONDS:

                return data.copy()


    # --------------------------------------------------------
    # DISK CACHE
    # --------------------------------------------------------

    disk_data = load_disk_cache(
        asset,
        period
    )

    if disk_data is not None:

        with _cache_lock:

            _data_cache[cache_key] = (
                time.time(),
                disk_data.copy()
            )

        return disk_data.copy()


    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------

    with _cache_lock:

        # Check again after acquiring lock.
        cached = _data_cache.get(cache_key)

        if cached is not None:

            timestamp, data = cached

            if time.time() - timestamp < CACHE_SECONDS:

                return data.copy()

        data = download_market_data(
            asset,
            period
        )

        _data_cache[cache_key] = (
            time.time(),
            data.copy()
        )

        return data.copy()


# ============================================================
# QUANTITATIVE METRICS
# ============================================================

def metrics(data):

    close = data["Close"].dropna()

    if len(close) < 2:
        raise ValueError(
            "Not enough historical data for analysis."
        )

    returns = close.pct_change().dropna()

    total_return = (
        close.iloc[-1] /
        close.iloc[0]
        - 1
    ) * 100

    # CAGR
    days = (
        close.index[-1] -
        close.index[0]
    ).days

    years = max(days / 365.25, 1 / 365.25)

    annual_return = (
        (close.iloc[-1] /
         close.iloc[0])
        ** (1 / years)
        - 1
    ) * 100

    volatility = (
        returns.std() *
        np.sqrt(252)
    ) * 100

    if returns.std() and not np.isnan(returns.std()):

        sharpe = (
            returns.mean() /
            returns.std()
        ) * np.sqrt(252)

    else:
        sharpe = 0

    running_max = close.cummax()

    drawdown = (
        close /
        running_max
        - 1
    )

    max_drawdown = (
        drawdown.min() * 100
    )

    return {
        "total_return": clean_number(
            total_return
        ),

        "annual_return": clean_number(
            annual_return
        ),

        "volatility": clean_number(
            volatility
        ),

        "sharpe": clean_number(
            sharpe
        ),

        "max_drawdown": clean_number(
            max_drawdown
        ),
    }


# ============================================================
# INDICATORS
# ============================================================

def add_indicators(
    data,
    fast=20,
    slow=50
):

    fast = max(2, int(fast))
    slow = max(
        fast + 1,
        int(slow)
    )

    df = data.copy()

    close = df["Close"]

    df["SMA Fast"] = (
        close
        .rolling(fast)
        .mean()
    )

    df["SMA Slow"] = (
        close
        .rolling(slow)
        .mean()
    )

    df["EMA Fast"] = (
        close
        .ewm(
            span=fast,
            adjust=False
        )
        .mean()
    )

    df["EMA Slow"] = (
        close
        .ewm(
            span=slow,
            adjust=False
        )
        .mean()
    )

    df["Daily Return"] = (
        close.pct_change()
    )

    df["Rolling Volatility"] = (
        df["Daily Return"]
        .rolling(30)
        .std()
        * np.sqrt(252)
    )

    df["Cumulative Return"] = (
        1 +
        df["Daily Return"].fillna(0)
    ).cumprod() - 1

    running_max = close.cummax()

    df["Drawdown"] = (
        close /
        running_max
        - 1
    )

    # Rolling return
    df["Rolling Return"] = (
        close /
        close.shift(30)
        - 1
    )

    return df


# ============================================================
# BACKTEST ENGINE
# ============================================================

def backtest(
    data,
    strategy,
    initial_capital=100000,
    transaction_cost=0.001,
    fast=20,
    slow=50
):

    if strategy not in STRATEGIES:
        strategy = "sma"

    initial_capital = max(
        float(initial_capital),
        1
    )

    transaction_cost = max(
        float(transaction_cost),
        0
    )

    df = add_indicators(
        data,
        fast,
        slow
    )

    close = df["Close"]

    # --------------------------------------------------------
    # STRATEGY SIGNALS
    # --------------------------------------------------------

    if strategy == "sma":

        signal = (
            df["SMA Fast"] >
            df["SMA Slow"]
        ).astype(int)

    elif strategy == "ema":

        signal = (
            df["EMA Fast"] >
            df["EMA Slow"]
        ).astype(int)

    elif strategy == "momentum":

        signal = (
            close >
            close.shift(20)
        ).astype(int)

    elif strategy == "mean_reversion":

        rolling_mean = (
            close
            .rolling(20)
            .mean()
        )

        signal = (
            close <
            rolling_mean * 0.97
        ).astype(int)

    else:

        signal = pd.Series(
            0,
            index=df.index
        )


    signal = signal.fillna(0)

    # --------------------------------------------------------
    # POSITION CHANGES
    # --------------------------------------------------------

    position_change = (
        signal
        .diff()
        .abs()
        .fillna(signal.abs())
    )

    # --------------------------------------------------------
    # RETURNS
    # --------------------------------------------------------

    asset_return = (
        close
        .pct_change()
        .fillna(0)
    )

    strategy_return = (
        signal.shift(1)
        .fillna(0)
        * asset_return
    )

    # Transaction costs
    strategy_return = (
        strategy_return -
        position_change *
        transaction_cost
    )

    # Avoid impossible negative multiplier
    strategy_return = strategy_return.clip(
        lower=-0.999
    )

    # --------------------------------------------------------
    # EQUITY
    # --------------------------------------------------------

    equity = (
        initial_capital *
        (
            1 +
            strategy_return
        ).cumprod()
    )

    benchmark = (
        initial_capital *
        (
            1 +
            asset_return
        ).cumprod()
    )

    result = df.copy()

    result["Signal"] = signal

    result["Strategy Return"] = (
        strategy_return
    )

    result["Equity"] = equity

    result["Benchmark"] = benchmark

    result["Drawdown"] = (
        equity /
        equity.cummax()
        - 1
    )

    # --------------------------------------------------------
    # STRATEGY METRICS
    # --------------------------------------------------------

    valid_returns = (
        strategy_return
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .dropna()
    )

    if (
        len(valid_returns) > 1
        and valid_returns.std() != 0
    ):

        sharpe = (
            valid_returns.mean() /
            valid_returns.std()
        ) * np.sqrt(252)

    else:

        sharpe = 0

    total_return = (
        equity.iloc[-1] /
        initial_capital
        - 1
    ) * 100

    benchmark_return = (
        benchmark.iloc[-1] /
        initial_capital
        - 1
    ) * 100

    max_drawdown = (
        result["Drawdown"]
        .min()
        * 100
    )

    trades = int(
        (
            position_change > 0
        ).sum()
    )

    strategy_volatility = (
        valid_returns.std()
        * np.sqrt(252)
        * 100
    )

    summary = {

        "final_value": clean_number(
            equity.iloc[-1]
        ),

        "return": clean_number(
            total_return
        ),

        "sharpe": clean_number(
            sharpe
        ),

        "volatility": clean_number(
            strategy_volatility
        ),

        "max_drawdown": clean_number(
            max_drawdown
        ),

        "trades": trades,

        "benchmark_return": clean_number(
            benchmark_return
        ),
    }

    return result, summary


# ============================================================
# CHART SERIALIZER
# ============================================================

def serialize_analysis(df):
    """
    Convert DataFrame to frontend-friendly arrays.
    """

    recent = df.tail(365)

    dates = []
    close = []
    sma_fast = []
    sma_slow = []
    ema_fast = []
    ema_slow = []
    daily_return = []
    volatility = []
    cumulative_return = []
    drawdown = []
    rolling_return = []

    for index, row in recent.iterrows():

        dates.append(
            index.strftime("%Y-%m-%d")
        )

        close.append(
            clean_number(row["Close"])
        )

        sma_fast.append(
            clean_number(row["SMA Fast"])
        )

        sma_slow.append(
            clean_number(row["SMA Slow"])
        )

        ema_fast.append(
            clean_number(row["EMA Fast"])
        )

        ema_slow.append(
            clean_number(row["EMA Slow"])
        )

        daily_return.append(
            clean_number(
                row["Daily Return"] * 100
            )
        )

        volatility.append(
            clean_number(
                row["Rolling Volatility"] * 100
            )
        )

        cumulative_return.append(
            clean_number(
                row["Cumulative Return"] * 100
            )
        )

        drawdown.append(
            clean_number(
                row["Drawdown"] * 100
            )
        )

        rolling_return.append(
            clean_number(
                row["Rolling Return"] * 100
            )
        )

    return {
        "dates": dates,
        "close": close,
        "sma_fast": sma_fast,
        "sma_slow": sma_slow,
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "daily_return": daily_return,
        "volatility": volatility,
        "cumulative_return": cumulative_return,
        "drawdown": drawdown,
        "rolling_return": rolling_return,
    }


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html",
        assets=ASSETS,
        strategies=STRATEGIES
    )


# ============================================================
# ANALYSIS API
# ============================================================

@app.route("/api/analysis")
def analysis():

    try:

        asset = request.args.get(
            "asset",
            "nvidia"
        )

        period = request.args.get(
            "period",
            "5y"
        )

        fast = safe_int(
            request.args.get("fast", 20),
            20
        )

        slow = safe_int(
            request.args.get("slow", 50),
            50
        )

        if asset not in ASSETS:
            asset = "nvidia"

        if period not in PERIOD_MAP:
            period = "5y"

        data = load_data(
            asset,
            period
        )

        data = add_indicators(
            data,
            fast,
            slow
        )

        m = metrics(data)

        chart = serialize_analysis(
            data
        )

        return jsonify({

            "status": "ok",

            "asset": ASSETS[asset]["name"],

            "ticker": ASSETS[asset]["ticker"],

            "metrics": m,

            **chart,

            "last_price": clean_number(
                data["Close"].iloc[-1]
            ),

            "last_date":
                data.index[-1].strftime(
                    "%Y-%m-%d"
                ),
        })

    except Exception as error:

        print(
            f"[ANALYSIS ERROR] {repr(error)}",
            flush=True
        )

        return jsonify({

            "status": "error",

            "error":
                "Market data is temporarily unavailable. "
                "Please try again later.",

        }), 503


# ============================================================
# BACKTEST API
# ============================================================

@app.route("/api/backtest")
def run_backtest():

    try:

        asset = request.args.get(
            "asset",
            "nvidia"
        )

        strategy = request.args.get(
            "strategy",
            "sma"
        )

        period = request.args.get(
            "period",
            "5y"
        )

        capital = safe_float(
            request.args.get(
                "capital",
                100000
            ),
            100000
        )

        # Support both names:
        # transaction_cost and cost
        cost = request.args.get(
            "transaction_cost"
        )

        if cost is None:
            cost = request.args.get(
                "cost",
                0.001
            )

        cost = safe_float(
            cost,
            0.001
        )

        fast = safe_int(
            request.args.get(
                "fast",
                20
            ),
            20
        )

        slow = safe_int(
            request.args.get(
                "slow",
                50
            ),
            50
        )

        if asset not in ASSETS:
            asset = "nvidia"

        if strategy not in STRATEGIES:
            strategy = "sma"

        if period not in PERIOD_MAP:
            period = "5y"

        data = load_data(
            asset,
            period
        )

        result, summary = backtest(
            data,
            strategy,
            capital,
            cost,
            fast,
            slow
        )

        recent = result.tail(365)

        dates = []
        strategy_equity = []
        benchmark_equity = []
        drawdown = []
        signals = []

        for index, row in recent.iterrows():

            dates.append(
                index.strftime("%Y-%m-%d")
            )

            strategy_equity.append(
                clean_number(
                    row["Equity"]
                )
            )

            benchmark_equity.append(
                clean_number(
                    row["Benchmark"]
                )
            )

            drawdown.append(
                clean_number(
                    row["Drawdown"] * 100
                )
            )

            signals.append(
                int(row["Signal"])
            )

        return jsonify({

            "status": "ok",

            "asset":
                ASSETS[asset]["name"],

            "strategy":
                STRATEGIES[strategy],

            "metrics":
                summary,

            "summary":
                summary,

            "dates":
                dates,

            "strategy_equity":
                strategy_equity,

            "benchmark_equity":
                benchmark_equity,

            "drawdown":
                drawdown,

            "signals":
                signals,

        })

    except Exception as error:

        print(
            f"[BACKTEST ERROR] {repr(error)}",
            flush=True
        )

        return jsonify({

            "status": "error",

            "error":
                "Backtest data is temporarily unavailable."

        }), 503


# ============================================================
# CORRELATION API
# ============================================================

@app.route("/api/correlation")
def correlation():

    try:

        period = request.args.get(
            "period",
            "5y"
        )

        series = {}

        for key, info in ASSETS.items():

            df = load_data(
                key,
                period
            )

            series[
                info["name"]
            ] = df["Close"].pct_change()

        returns = (
            pd.DataFrame(series)
            .dropna()
        )

        if returns.empty:
            raise ValueError(
                "Correlation data unavailable."
            )

        corr = returns.corr()

        labels = list(
            corr.columns
        )

        matrix = [
            [
                clean_number(
                    corr.loc[row, col]
                )
                for col in labels
            ]
            for row in labels
        ]

        # ----------------------------------------------------
        # Rolling BTC / NVIDIA correlation
        # ----------------------------------------------------

        rolling_data = []

        if (
            "Bitcoin" in returns.columns
            and
            "NVIDIA" in returns.columns
        ):

            rolling = (
                returns["Bitcoin"]
                .rolling(60)
                .corr(
                    returns["NVIDIA"]
                )
                .dropna()
                .tail(365)
            )

            rolling_dates = []
            rolling_values = []

            for index, value in rolling.items():

                rolling_dates.append(
                    index.strftime(
                        "%Y-%m-%d"
                    )
                )

                rolling_values.append(
                    clean_number(value)
                )

        else:

            rolling_dates = []
            rolling_values = []

        return jsonify({

            "status": "ok",

            "labels": labels,

            "matrix": matrix,

            "rolling_dates":
                rolling_dates,

            "rolling_correlation":
                rolling_values,

            # Compatibility with older frontend
            "rolling_btc_nvidia": [
                {
                    "date": date,
                    "value": value
                }

                for date, value
                in zip(
                    rolling_dates,
                    rolling_values
                )
            ],
        })

    except Exception as error:

        print(
            f"[CORRELATION ERROR] {repr(error)}",
            flush=True
        )

        return jsonify({

            "status": "error",

            "error":
                "Correlation data is temporarily unavailable."

        }), 503


# ============================================================
# HEALTH
# ============================================================

@app.route("/api/health")
def health():

    return jsonify({

        "status": "ok",

        "service":
            "MarketLab Quantitative Financial Intelligence Platform",

        "timestamp":
            datetime.utcnow().isoformat() + "Z",

    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "status": "error",
        "error": "Endpoint not found."
    }), 404


@app.errorhandler(500)
def internal_error(error):

    print(
        f"[500 ERROR] {repr(error)}",
        flush=True
    )

    return jsonify({

        "status": "error",

        "error":
            "An internal server error occurred."

    }), 500


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
