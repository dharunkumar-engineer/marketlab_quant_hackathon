# MarketLab — Quantitative Multi-Asset Research & Backtesting

A small, practical web application for historical analysis of Gold, Bitcoin and NVIDIA.

## What it does

- Downloads historical market data
- Calculates SMA and EMA
- Calculates returns, annualized volatility, Sharpe ratio and maximum drawdown
- Shows daily return and drawdown charts
- Builds a cross-asset correlation matrix
- Shows rolling Bitcoin/NVIDIA correlation
- Backtests SMA crossover, EMA trend, momentum and mean-reversion strategies
- Includes initial capital and transaction costs
- Compares a strategy with Buy & Hold
- Keeps the interface focused on research rather than trading recommendations

## Run locally

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install:

```bash
pip install -r requirements.txt
```

Run:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Deploy on Render

1. Create a GitHub repository.
2. Upload all files from this project.
3. On Render, choose **New Web Service**.
4. Connect the GitHub repository.
5. Build command:

```text
pip install -r requirements.txt
```

6. Start command:

```text
gunicorn --timeout 120 --workers 1 app:app
```

7. Deploy.

The included `render.yaml` can also be used with Render Blueprint deployment.

## Notes

Market data is requested from Yahoo Finance through `yfinance`, so the deployed service needs outbound internet access.

This project is intended for historical research and hackathon demonstration. Backtests are simulations and are not guarantees of future returns.
