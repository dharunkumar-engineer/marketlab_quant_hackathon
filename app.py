import os
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request


# ============================================================
# APPLICATION
# ============================================================

app = Flask(__name__)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


# ============================================================
# ASSETS
# ============================================================

ASSETS = {
    "gold": {
        "name": "Gold",
        "ticker": "GC=F",
        "file": "gold.csv",
    },
    "bitcoin": {
        "name": "Bitcoin",
        "ticker": "BTC-USD",
        "file": "bitcoin.csv",
    },
    "nvidia": {
        "name": "NVIDIA",
        "ticker": "NVDA",
        "file": "nvidia.csv",
    },
}


STRATEGIES = {
    "sma": "SMA Crossover",
    "ema": "EMA Trend",
    "momentum": "Momentum",
    "mean_reversion": "Mean Reversion",
}


PERIOD_DAYS = {
    "1y": 365,
    "3y": 365 * 3,
    "5y": 365 * 5,
    "10y": 365 * 10,
    "max": None,
}


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clean_number(value):
    """
    Convert pandas/numpy numeric values into JSON-safe numbers.
    """
    if value is None:
        return None

    try:
        if pd.isna(value) or np.isinf(value):
            return None

        return round(float(value), 6)

    except (TypeError, ValueError):
        return None


def normalize_column_name(column):
    """
    Normalize CSV column names.

    Examples:
        Adj Close -> adj_close
        Date      -> date
        Trading Date -> trading_date
    """
    return (
        str(column)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def find_column(columns, possible_names):
    """
    Find a column using several possible names.
    """
    normalized = {
        normalize_column_name(col): col
        for col in columns
    }

    for name in possible_names:
        key = normalize_column_name(name)

        if key in normalized:
            return normalized[key]

    return None


# ============================================================
# CSV LOADING
# ============================================================

def load_data(asset="nvidia", period="5y"):
    """
    Load historical market data from a local CSV file.

    Supports:
    1. Normal CSV files
    2. Yahoo Finance-style CSV files with a two-row header

    No external API or Yahoo Finance dependency is used.
    """

    if asset not in ASSETS:
        raise ValueError(f"Unknown asset: {asset}")

    file_name = ASSETS[asset]["file"]
    file_path = DATA_DIR / file_name

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {file_name}. "
            f"Please place it inside the data folder."
        )

    # ========================================================
    # READ CSV
    # ========================================================

    try:

        # First try normal CSV format
        raw = pd.read_csv(
            file_path,
            low_memory=False
        )

        # Check first column
        first_col = str(
            raw.columns[0]
        ).strip().lower()

        # ----------------------------------------------------
        # Yahoo Finance-style CSV detection
        # ----------------------------------------------------
        #
        # Example:
        #
        # Price,Adj Close,Close,High,Low,Open,Volume
        # Ticker,NVDA,NVDA,NVDA,NVDA,NVDA,NVDA
        # Date
        # 2018-01-02,...
        #
        # In this format Date is the index and the header
        # contains two rows.
        # ----------------------------------------------------

        if first_col not in [
            "date",
            "datetime",
            "timestamp",
            "time",
            "day"
        ]:

            try:

                yahoo_raw = pd.read_csv(
                    file_path,
                    header=[0, 1],
                    index_col=0,
                    low_memory=False
                )

                if isinstance(
                    yahoo_raw.columns,
                    pd.MultiIndex
                ):

                    yahoo_raw.columns = [
                        str(col[0]).strip()
                        for col in yahoo_raw.columns
                    ]

                yahoo_raw.index.name = "Date"

                raw = yahoo_raw.reset_index()

            except Exception:
                # Keep the normal CSV if multi-header
                # parsing is unsuccessful.
                pass

    except Exception as exc:

        raise ValueError(
            f"Could not read {file_name}: {exc}"
        )

    # ========================================================
    # EMPTY CHECK
    # ========================================================

    if raw.empty:
        raise ValueError(
            f"{file_name} is empty."
        )

    # ========================================================
    # LOCATE DATE COLUMN
    # ========================================================

    date_col = find_column(
        raw.columns,
        [
            "Date",
            "Datetime",
            "Timestamp",
            "Trading Date",
            "Trade Date",
            "Date Time",
            "Date/Time",
            "Time",
            "Day",
            "Trade_Date",
            "Trading_Date",
            "Price Date",
            "Price_Date",
            "DateTime",
            "Timestamp UTC",
        ],
    )

    # ========================================================
    # FALLBACK DATE DETECTION
    # ========================================================

    if date_col is None and len(raw.columns) > 0:

        first_column = raw.columns[0]

        parsed_dates = pd.to_datetime(
            raw[first_column],
            errors="coerce"
        )

        if (
            parsed_dates.notna().mean()
            >= 0.8
        ):

            date_col = first_column

    # ========================================================
    # LOCATE PRICE COLUMNS
    # ========================================================

    open_col = find_column(
        raw.columns,
        [
            "Open",
            "Open Price",
        ]
    )

    high_col = find_column(
        raw.columns,
        [
            "High",
            "High Price",
        ]
    )

    low_col = find_column(
        raw.columns,
        [
            "Low",
            "Low Price",
        ]
    )

    close_col = find_column(
        raw.columns,
        [
            "Close",
            "Close Price",
            "Adj Close",
            "Adjusted Close",
        ]
    )

    volume_col = find_column(
        raw.columns,
        [
            "Volume",
            "Volume Traded",
            "Vol.",
            "Vol",
        ]
    )

    # ========================================================
    # VALIDATE REQUIRED COLUMNS
    # ========================================================

    if date_col is None:

        raise ValueError(
            f"{file_name}: Date column could not be found. "
            f"Available columns: {list(raw.columns)}"
        )

    if close_col is None:

        raise ValueError(
            f"{file_name}: Close column could not be found. "
            f"Available columns: {list(raw.columns)}"
        )

    # ========================================================
    # BUILD STANDARDIZED DATAFRAME
    # ========================================================

    data = pd.DataFrame()

    data["Date"] = pd.to_datetime(
        raw[date_col],
        errors="coerce"
    )

    data["Close"] = pd.to_numeric(
        raw[close_col],
        errors="coerce"
    )

    # Open
    if open_col is not None:

        data["Open"] = pd.to_numeric(
            raw[open_col],
            errors="coerce"
        )

    else:

        data["Open"] = data["Close"]

    # High
    if high_col is not None:

        data["High"] = pd.to_numeric(
            raw[high_col],
            errors="coerce"
        )

    else:

        data["High"] = data["Close"]

    # Low
    if low_col is not None:

        data["Low"] = pd.to_numeric(
            raw[low_col],
            errors="coerce"
        )

    else:

        data["Low"] = data["Close"]

    # Volume
    if volume_col is not None:

        data["Volume"] = pd.to_numeric(
            raw[volume_col],
            errors="coerce"
        )

    else:

        data["Volume"] = 0

    # ========================================================
    # CLEAN DATA
    # ========================================================

    data = data.dropna(
        subset=[
            "Date",
            "Close"
        ]
    )

    data = data.sort_values(
        "Date"
    )

    data = data.drop_duplicates(
        subset=["Date"],
        keep="last"
    )

    data = data.set_index(
        "Date"
    )

    # Remove invalid prices
    data = data[
        data["Close"] > 0
    ]

    # ========================================================
    # APPLY PERIOD
    # ========================================================

    if period not in PERIOD_DAYS:
        period = "5y"

    days = PERIOD_DAYS[period]

    if (
        days is not None
        and not data.empty
    ):

        latest_date = data.index.max()

        start_date = (
            latest_date
            - pd.Timedelta(days=days)
        )

        filtered = data[
            data.index >= start_date
        ]

        if not filtered.empty:
            data = filtered

# ========================================================
# FINAL VALIDATION
# ========================================================

    if data.empty:

        raise ValueError(
            f"No usable data available for {asset}."
        )

    return data


# ============================================================
# INDICATORS
# ============================================================

def add_indicators(data, fast=20, slow=50):
    """
    Add quantitative indicators required by the project.
    """

    if fast < 2:
        fast = 2

    if slow <= fast:
        slow = fast + 1

    # Make an independent copy
    df = data.copy(deep=True)

    close = df["Close"]

    # --------------------------------------------------------
    # Moving averages
    # --------------------------------------------------------

    df.loc[:, "SMA Fast"] = (
        close.rolling(
            window=fast,
            min_periods=fast
        ).mean()
    )

    df.loc[:, "SMA Slow"] = (
        close.rolling(
            window=slow,
            min_periods=slow
        ).mean()
    )

    df.loc[:, "EMA Fast"] = (
        close.ewm(
            span=fast,
            adjust=False
        ).mean()
    )

    df.loc[:, "EMA Slow"] = (
        close.ewm(
            span=slow,
            adjust=False
        ).mean()
    )

    # --------------------------------------------------------
    # Daily returns
    # --------------------------------------------------------

    df.loc[:, "Daily Return"] = (
        close.pct_change()
    )

    # --------------------------------------------------------
    # Cumulative returns
    # --------------------------------------------------------

    df.loc[:, "Cumulative Return"] = (
        1 + df["Daily Return"].fillna(0)
    ).cumprod() - 1

    # --------------------------------------------------------
    # Rolling volatility
    # --------------------------------------------------------

    df.loc[:, "Rolling Volatility"] = (
        df["Daily Return"]
        .rolling(
            window=30,
            min_periods=30
        )
        .std()
        * np.sqrt(252)
    )

    # --------------------------------------------------------
    # Rolling returns
    # --------------------------------------------------------

    df.loc[:, "Rolling Return 30D"] = (
        close.pct_change(30)
    )

    df.loc[:, "Rolling Return 90D"] = (
        close.pct_change(90)
    )

    # --------------------------------------------------------
    # Running maximum
    # --------------------------------------------------------

    df.loc[:, "Running Max"] = (
        close.cummax()
    )

    # --------------------------------------------------------
    # Drawdown
    # --------------------------------------------------------

    df.loc[:, "Drawdown"] = (
        close / df["Running Max"] - 1
    )

    return df

# ============================================================
# PERFORMANCE METRICS
# ============================================================

def calculate_sharpe(returns):
    """
    Annualized Sharpe ratio using a zero risk-free rate.
    """

    returns = pd.Series(returns).dropna()

    if len(returns) < 2:
        return 0.0

    std = returns.std()

    if std == 0 or pd.isna(std):
        return 0.0

    return (
        returns.mean() / std
    ) * np.sqrt(252)


def calculate_metrics(data):
    """
    Calculate historical performance metrics.
    """

    close = data["Close"].dropna()

    if len(close) < 2:
        return {
            "total_return": 0,
            "annual_return": 0,
            "volatility": 0,
            "sharpe": 0,
            "max_drawdown": 0,
        }

    returns = close.pct_change().dropna()

    # Total return
    total_return = (
        close.iloc[-1] / close.iloc[0] - 1
    )

    # CAGR
    days = (
        close.index[-1] - close.index[0]
    ).days

    years = max(days / 365.25, 1 / 365.25)

    annual_return = (
        (close.iloc[-1] / close.iloc[0])
        ** (1 / years)
        - 1
    )

    # Annualized volatility
    volatility = (
        returns.std() * np.sqrt(252)
    )

    # Sharpe
    sharpe = calculate_sharpe(returns)

    # Maximum drawdown
    running_max = close.cummax()

    drawdown = (
        close / running_max - 1
    )

    max_drawdown = drawdown.min()

    return {
        "total_return": clean_number(
            total_return * 100
        ),
        "annual_return": clean_number(
            annual_return * 100
        ),
        "volatility": clean_number(
            volatility * 100
        ),
        "sharpe": clean_number(
            sharpe
        ),
        "max_drawdown": clean_number(
            max_drawdown * 100
        ),
    }


# ============================================================
# MARKET REGIME
# ============================================================

def detect_market_regime(data):
    """
    Classify the current market environment using
    trend and volatility.

    Regimes:
        Bull
        Bear
        High Volatility
        Low Volatility
    """

    df = add_indicators(data)

    if len(df) < 60:
        return "Insufficient Data"

    latest = df.iloc[-1]

    price = latest["Close"]
    sma = latest["SMA Slow"]
    volatility = latest["Rolling Volatility"]

    if pd.isna(sma) or pd.isna(volatility):
        return "Insufficient Data"

    historical_vol = (
        df["Rolling Volatility"]
        .dropna()
    )

    if historical_vol.empty:
        return "Insufficient Data"

    median_vol = historical_vol.median()

    if volatility > median_vol * 1.5:
        return "High Volatility"

    if price > sma:
        return "Bull"

    if price < sma:
        return "Bear"

    if volatility < median_vol * 0.75:
        return "Low Volatility"

    return "Low Volatility"


# ============================================================
# BACKTESTING
# ============================================================

def create_strategy_signal(
    df,
    strategy,
    fast=20,
    slow=50
):
    """
    Generate trading signals.

    Signal:
        1 = invested
        0 = out of market
    """

    close = df["Close"]

    if strategy == "sma":

        signal = (
            df["SMA Fast"]
            > df["SMA Slow"]
        ).astype(int)

    elif strategy == "ema":

        signal = (
            df["EMA Fast"]
            > df["EMA Slow"]
        ).astype(int)

    elif strategy == "momentum":

        lookback = max(fast, 20)

        signal = (
            close
            > close.shift(lookback)
        ).astype(int)

    elif strategy == "mean_reversion":

        mean = (
            close
            .rolling(fast)
            .mean()
        )

        # Buy when price is at least 3%
        # below its moving average.
        signal = (
            close
            < mean * 0.97
        ).astype(int)

    else:
        raise ValueError(
            f"Unknown strategy: {strategy}"
        )

    return signal.fillna(0)


def backtest(
    data,
    strategy,
    initial_capital=100000,
    transaction_cost=0.001,
    fast=20,
    slow=50
):
    """
    Run a historical strategy backtest.

    Important:
    The signal is shifted by one trading day
    to reduce look-ahead bias.
    """

    if initial_capital <= 0:
        raise ValueError(
            "Initial capital must be greater than zero."
        )

    if transaction_cost < 0:
        raise ValueError(
            "Transaction cost cannot be negative."
        )

    df = add_indicators(
        data,
        fast,
        slow
    )

    close = df["Close"]

    # Strategy signal
    signal = create_strategy_signal(
        df,
        strategy,
        fast,
        slow
    )

    # Position change
    position_change = (
        signal.diff()
        .abs()
        .fillna(signal.abs())
    )

    # Daily asset return
    asset_return = (
        close
        .pct_change()
        .fillna(0)
    )

    # Use previous day's signal
    # to avoid look-ahead bias.
    strategy_position = (
        signal.shift(1)
        .fillna(0)
    )

    strategy_return = (
        strategy_position
        * asset_return
    )

    # Transaction costs
    strategy_return = (
        strategy_return
        - position_change * transaction_cost
    )

    # Portfolio equity
    equity = (
        initial_capital
        * (1 + strategy_return)
        .cumprod()
    )

    # Buy and hold benchmark
    benchmark = (
        initial_capital
        * (1 + asset_return)
        .cumprod()
    )

    # Strategy drawdown
    strategy_running_max = (
        equity.cummax()
    )

    drawdown = (
        equity
        / strategy_running_max
        - 1
    )

    # Add results
    result = df.copy()

    result["Signal"] = signal
    result["Position"] = strategy_position
    result["Asset Return"] = asset_return
    result["Strategy Return"] = strategy_return
    result["Equity"] = equity
    result["Benchmark"] = benchmark
    result["Drawdown"] = drawdown

    # --------------------------------------------------------
    # Strategy metrics
    # --------------------------------------------------------

    final_value = equity.iloc[-1]

    strategy_total_return = (
        final_value
        / initial_capital
        - 1
    )

    benchmark_return = (
        benchmark.iloc[-1]
        / initial_capital
        - 1
    )

    strategy_sharpe = calculate_sharpe(
        strategy_return
    )

    max_drawdown = drawdown.min()

    number_of_trades = int(
        (position_change > 0).sum()
    )

    # Winning trading days
    active_returns = strategy_return[
        strategy_position > 0
    ]

    winning_days = int(
        (active_returns > 0).sum()
    )

    losing_days = int(
        (active_returns < 0).sum()
    )

    summary = {
        "initial_capital": clean_number(
            initial_capital
        ),
        "final_value": clean_number(
            final_value
        ),
        "return": clean_number(
            strategy_total_return * 100
        ),
        "sharpe": clean_number(
            strategy_sharpe
        ),
        "max_drawdown": clean_number(
            max_drawdown * 100
        ),
        "trades": number_of_trades,
        "winning_days": winning_days,
        "losing_days": losing_days,
        "benchmark_return": clean_number(
            benchmark_return * 100
        ),
    }

    return result, summary


# ============================================================
# CHART DATA
# ============================================================

def build_analysis_chart(data, max_rows=365):
    """
    Prepare chart-friendly JSON data.
    """

    if data.empty:
        return []

    recent = data.tail(max_rows)

    chart = []

    for idx, row in recent.iterrows():

        chart.append({
            "date": idx.strftime("%Y-%m-%d"),

            "open": clean_number(
                row.get("Open")
            ),

            "high": clean_number(
                row.get("High")
            ),

            "low": clean_number(
                row.get("Low")
            ),

            "close": clean_number(
                row.get("Close")
            ),

            "volume": clean_number(
                row.get("Volume")
            ),

            "sma_fast": clean_number(
                row.get("SMA Fast")
            ),

            "sma_slow": clean_number(
                row.get("SMA Slow")
            ),

            "ema_fast": clean_number(
                row.get("EMA Fast")
            ),

            "ema_slow": clean_number(
                row.get("EMA Slow")
            ),

            "return": clean_number(
                row.get("Daily Return", 0) * 100
            ),

            "cumulative_return": clean_number(
                row.get("Cumulative Return", 0) * 100
            ),

            "volatility": clean_number(
                row.get("Rolling Volatility", 0) * 100
            ),

            "drawdown": clean_number(
                row.get("Drawdown", 0) * 100
            ),

            "rolling_return_30d": clean_number(
                row.get("Rolling Return 30D", 0) * 100
            ),

            "rolling_return_90d": clean_number(
                row.get("Rolling Return 90D", 0) * 100
            ),
        })

    return chart


def build_backtest_chart(result, max_rows=365):
    """
    Prepare backtest chart data.
    """

    recent = result.tail(max_rows)

    chart = []

    for idx, row in recent.iterrows():

        chart.append({
            "date": idx.strftime("%Y-%m-%d"),

            "equity": clean_number(
                row.get("Equity")
            ),

            "benchmark": clean_number(
                row.get("Benchmark")
            ),

            "drawdown": clean_number(
                row.get("Drawdown", 0) * 100
            ),

            "signal": int(
                row.get("Signal", 0)
            ),

            "close": clean_number(
                row.get("Close")
            ),
        })

    return chart


# ============================================================
# ERROR RESPONSE
# ============================================================

def error_response(message, status_code=400):
    return jsonify({
        "status": "error",
        "message": str(message),
    }), status_code


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template(
        "index.html",
        assets=ASSETS,
        strategies=STRATEGIES
    )


# ------------------------------------------------------------
# Assets API
# ------------------------------------------------------------

@app.route("/api/assets")
def assets_api():

    result = {}

    for key, info in ASSETS.items():

        file_path = DATA_DIR / info["file"]

        available = file_path.exists()

        rows = 0
        start_date = None
        end_date = None

        if available:

            try:
                df = load_data(
                    key,
                    "max"
                )

                rows = len(df)

                if not df.empty:
                    start_date = (
                        df.index.min()
                        .strftime("%Y-%m-%d")
                    )

                    end_date = (
                        df.index.max()
                        .strftime("%Y-%m-%d")
                    )

            except Exception:
                available = False

        result[key] = {
            "name": info["name"],
            "ticker": info["ticker"],
            "file": info["file"],
            "available": available,
            "rows": rows,
            "start_date": start_date,
            "end_date": end_date,
        }

    return jsonify(result)


# ------------------------------------------------------------
# Analysis API
# ------------------------------------------------------------

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

        fast = int(
            request.args.get(
                "fast",
                20
            )
        )

        slow = int(
            request.args.get(
                "slow",
                50
            )
        )

        if asset not in ASSETS:
            return error_response(
                "Invalid asset."
            )

        if period not in PERIOD_DAYS:
            return error_response(
                "Invalid period."
            )

        if fast < 2:
            return error_response(
                "Fast moving-average period must be at least 2."
            )

        if slow <= fast:
            return error_response(
                "Slow moving-average period must be greater than fast period."
            )

        data = load_data(
            asset,
            period
        )

        data = add_indicators(
            data,
            fast,
            slow
        )

        metrics = calculate_metrics(
            data
        )

        regime = detect_market_regime(
            data
        )

        chart = build_analysis_chart(
            data
        )

        return jsonify({

            "status": "ok",

            "asset": ASSETS[asset]["name"],

            "ticker": ASSETS[asset]["ticker"],

            "period": period,

            "metrics": metrics,

            "regime": regime,

            "last_price": clean_number(
                data["Close"].iloc[-1]
            ),

            "last_date": data.index[-1].strftime(
                "%Y-%m-%d"
            ),

            "data_points": len(data),

            "chart": chart,
        })

    except FileNotFoundError as exc:

        return error_response(
            str(exc),
            404
        )

    except Exception as exc:

        return error_response(
            str(exc),
            500
        )


# ------------------------------------------------------------
# Backtesting API
# ------------------------------------------------------------

@app.route("/api/backtest", methods=["GET"])
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

        capital = float(
            request.args.get(
                "capital",
                100000
            )
        )

        cost = float(
            request.args.get(
                "cost",
                0.001
            )
        )

        fast = int(
            request.args.get(
                "fast",
                20
            )
        )

        slow = int(
            request.args.get(
                "slow",
                50
            )
        )

        # Validation
        if asset not in ASSETS:
            return error_response(
                "Invalid asset."
            )

        if strategy not in STRATEGIES:
            return error_response(
                "Invalid strategy."
            )

        if period not in PERIOD_DAYS:
            return error_response(
                "Invalid period."
            )

        if capital <= 0:
            return error_response(
                "Capital must be greater than zero."
            )

        if cost < 0:
            return error_response(
                "Transaction cost cannot be negative."
            )

        if fast < 2:
            return error_response(
                "Fast period must be at least 2."
            )

        if slow <= fast:
            return error_response(
                "Slow period must be greater than fast period."
            )

        data = load_data(
            asset,
            period
        )

        result, summary = backtest(
            data=data,
            strategy=strategy,
            initial_capital=capital,
            transaction_cost=cost,
            fast=fast,
            slow=slow
        )

        chart = build_backtest_chart(
            result
        )

        return jsonify({

            "status": "ok",

            "asset": ASSETS[asset]["name"],

            "ticker": ASSETS[asset]["ticker"],

            "strategy": STRATEGIES[strategy],

            "period": period,

            "parameters": {
                "initial_capital": capital,
                "transaction_cost": cost,
                "fast_period": fast,
                "slow_period": slow,
            },

            "summary": summary,

            "chart": chart,
        })

    except FileNotFoundError as exc:

        return error_response(
            str(exc),
            404
        )

    except ValueError as exc:

        return error_response(
            str(exc),
            400
        )

    except Exception as exc:

        return error_response(
            str(exc),
            500
        )

# ------------------------------------------------------------
# Correlation API
# ------------------------------------------------------------

@app.route("/api/correlation")
def correlation():

    try:

        period = request.args.get("period", "5y")

        if period not in PERIOD_DAYS:
            return error_response(
                "Invalid period."
            )

        returns_list = []

        for key, info in ASSETS.items():

            # Load asset data
            data = load_data(
                key,
                period
            )

            if data is None or data.empty:
                return error_response(
                    f"No data available for {info['name']}."
                )

            # Make independent copy
            data = data.copy(deep=True)

            # Normalize dates
            data.index = pd.to_datetime(
                data.index,
                errors="coerce"
            ).normalize()

            # Remove invalid dates
            data = data[
                data.index.notna()
            ]

            # Remove duplicate dates
            data = data[
                ~data.index.duplicated(
                    keep="last"
                )
            ]

            # Sort by date
            data = data.sort_index()

            # Make sure Close is numeric
            data.loc[:, "Close"] = pd.to_numeric(
                data["Close"],
                errors="coerce"
            )

            # Remove invalid prices
            data = data.dropna(
                subset=["Close"]
            )

            if len(data) < 2:
                return error_response(
                    f"Not enough price data for {info['name']}."
                )

            # Daily returns
            returns = (
                data["Close"]
                .pct_change()
                .replace(
                    [np.inf, -np.inf],
                    np.nan
                )
                .dropna()
            )

            returns.name = info["name"]

            returns_list.append(
                returns
            )

        # ----------------------------------------------------
        # Combine returns
        # ----------------------------------------------------

        returns_df = pd.concat(
            returns_list,
            axis=1,
            join="inner"
        )

        returns_df = returns_df.sort_index()

        # Remove rows containing missing values
        returns_df = returns_df.dropna(
            how="any"
        )

        # ----------------------------------------------------
        # Validate overlapping data
        # ----------------------------------------------------

        if returns_df.empty:

            return error_response(
                "No common dates found between Gold, Bitcoin and NVIDIA."
            )

        if len(returns_df) < 2:

            return error_response(
                "Not enough overlapping dates to calculate correlation."
            )

        # ----------------------------------------------------
        # Correlation matrix
        # ----------------------------------------------------

        corr = returns_df.corr()

        matrix = {}

        for row in corr.index:

            matrix[row] = {}

            for col in corr.columns:

                value = corr.loc[row, col]

                matrix[row][col] = clean_number(
                    value
                )

        # ----------------------------------------------------
        # Bitcoin vs NVIDIA rolling correlation
        # ----------------------------------------------------

        rolling_data = []

        if (
            "Bitcoin" in returns_df.columns
            and
            "NVIDIA" in returns_df.columns
        ):

            rolling = (
                returns_df["Bitcoin"]
                .rolling(
                    window=60,
                    min_periods=20
                )
                .corr(
                    returns_df["NVIDIA"]
                )
                .dropna()
            )

            # Keep latest 365 observations
            rolling = rolling.tail(365)

            for idx, value in rolling.items():

                rolling_data.append({

                    "date": idx.strftime(
                        "%Y-%m-%d"
                    ),

                    "value": clean_number(
                        value
                    ),

                })

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return jsonify({

            "status": "ok",

            "period": period,

            "matrix": matrix,

            "rolling_btc_nvidia": rolling_data,

            "data_points": int(
                len(returns_df)
            ),

        })

    except FileNotFoundError as exc:

        return error_response(
            str(exc),
            404
        )

    except Exception as exc:

        # Print complete error to Render logs
        print(
            "CORRELATION ERROR:",
            repr(exc)
        )

        return error_response(
            f"Correlation calculation failed: {exc}",
            500
        )
# ------------------------------------------------------------
# Market Regimes API
# ------------------------------------------------------------

@app.route("/api/regimes")
def regimes():

    try:

        period = request.args.get(
            "period",
            "5y"
        )

        result = {}

        for key, info in ASSETS.items():

            data = load_data(
                key,
                period
            )

            regime = detect_market_regime(
                data
            )

            result[key] = {
                "asset": info["name"],
                "regime": regime,
                "last_price": clean_number(
                    data["Close"].iloc[-1]
                ),
                "last_date": data.index[-1].strftime(
                    "%Y-%m-%d"
                ),
            }

        return jsonify({
            "status": "ok",
            "period": period,
            "regimes": result,
        })

    except FileNotFoundError as exc:

        return error_response(
            str(exc),
            404
        )

    except Exception as exc:

        return error_response(
            str(exc),
            500
        )


# ------------------------------------------------------------
# Health API
# ------------------------------------------------------------

@app.route("/api/health")
def health():

    files = {}

    for key, info in ASSETS.items():

        path = DATA_DIR / info["file"]

        files[key] = {
            "file": info["file"],
            "available": path.exists(),
        }

    all_available = all(
        item["available"]
        for item in files.values()
    )

    return jsonify({

        "status": "ok",

        "data_source": "local_csv",

        "external_market_api": False,

        "datasets_ready": all_available,

        "files": files,
    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    if request.path.startswith("/api/"):
        return error_response(
            "API endpoint not found.",
            404
        )

    return error


@app.errorhandler(500)
def internal_error(error):

    if request.path.startswith("/api/"):
        return error_response(
            "Internal server error.",
            500
        )

    return error


# ============================================================
# START APPLICATION
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
