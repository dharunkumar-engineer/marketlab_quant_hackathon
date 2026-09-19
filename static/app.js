/* =========================================================
   MARKETLAB — FRONTEND APPLICATION
   ========================================================= */

"use strict";

/* =========================================================
   GLOBAL CONFIGURATION
   ========================================================= */

const API = {
    analysis: "/api/analysis",
    backtest: "/api/backtest",
    correlation: "/api/correlation",
    health: "/api/health"
};

let currentAnalysis = null;
let currentBacktest = null;

/* =========================================================
   DOM HELPERS
   ========================================================= */

function $(id) {
    return document.getElementById(id);
}

function getValue(id, fallback = "") {
    const element = $(id);
    return element ? element.value : fallback;
}

function setText(id, value) {
    const element = $(id);

    if (element) {
        element.textContent = value;
    }
}

function safeNumber(value, fallback = 0) {
    const number = Number(value);

    return Number.isFinite(number) ? number : fallback;
}

function formatNumber(value, decimals = 2) {
    const number = safeNumber(value);

    return number.toLocaleString("en-US", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

function formatPercent(value, decimals = 2) {
    const number = safeNumber(value);

    return `${number.toFixed(decimals)}%`;
}

function formatCurrency(value) {
    const number = safeNumber(value);

    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2
    }).format(number);
}

/* =========================================================
   TOAST
   ========================================================= */

function showToast(message, type = "error") {
    let container = document.querySelector(".toast-container");

    if (!container) {
        container = document.createElement("div");
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");

    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(8px)";

        setTimeout(() => {
            toast.remove();
        }, 200);
    }, 4500);
}

/* =========================================================
   API REQUEST
   ========================================================= */

async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Accept": "application/json",
            ...(options.headers || {})
        }
    });

    const contentType = response.headers.get("content-type") || "";

    let data;

    if (contentType.includes("application/json")) {
        data = await response.json();
    } else {
        const text = await response.text();

        throw new Error(
            `Server returned an unexpected response (${response.status}). ${text.slice(0, 150)}`
        );
    }

    if (!response.ok) {
        throw new Error(
            data.error ||
            data.message ||
            `Request failed with status ${response.status}`
        );
    }

    return data;
}

/* =========================================================
   PLOTLY DEFAULTS
   ========================================================= */

const plotLayout = {
    margin: {
        l: 45,
        r: 20,
        t: 20,
        b: 40
    },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: {
        family: "Inter, Arial, sans-serif",
        size: 11,
        color: "#6b7280"
    },
    hovermode: "x unified",
    xaxis: {
        gridcolor: "#eef0f3",
        zeroline: false
    },
    yaxis: {
        gridcolor: "#eef0f3",
        zeroline: false
    }
};

const plotConfig = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: [
        "lasso2d",
        "select2d",
        "autoScale2d"
    ]
};

/* =========================================================
   PLOTLY SAFE RENDER
   ========================================================= */

function renderChart(elementId, traces, layout = {}) {
    const element = $(elementId);

    if (!element) {
        return;
    }

    if (!window.Plotly) {
        console.error("Plotly is not loaded.");
        return;
    }

    try {
        Plotly.react(
            element,
            traces,
            {
                ...plotLayout,
                ...layout
            },
            plotConfig
        );
    } catch (error) {
        console.error(`Chart error: ${elementId}`, error);
    }
}

/* =========================================================
   ANALYSIS
   ========================================================= */

async function loadAnalysis() {
    const asset = getValue("asset", "gold");
    const period = getValue("period", "2y");
    const fast = getValue("fast", "20");
    const slow = getValue("slow", "50");

    try {
        const params = new URLSearchParams({
            asset,
            period,
            fast,
            slow
        });

        const data = await fetchJSON(
            `${API.analysis}?${params.toString()}`
        );

        currentAnalysis = data;

        updateAnalysisMetrics(data);
        renderPriceChart(data);
        renderReturnsChart(data);
        renderDrawdownChart(data);

        setStatus(true, "Analysis loaded");

    } catch (error) {
        console.error("Analysis error:", error);

        setStatus(false, "Data unavailable");

        showToast(
            "Market data is temporarily unavailable. Yahoo Finance may be rate-limiting requests.",
            "error"
        );
    }
}

/* =========================================================
   UPDATE METRICS
   ========================================================= */

function updateAnalysisMetrics(data) {
    const metrics = data.metrics || {};

    setText(
        "metric-return",
        formatPercent(metrics.total_return)
    );

    setText(
        "metric-annual-return",
        formatPercent(metrics.annual_return)
    );

    setText(
        "metric-volatility",
        formatPercent(metrics.volatility)
    );

    setText(
        "metric-sharpe",
        formatNumber(metrics.sharpe, 2)
    );

    setText(
        "metric-drawdown",
        formatPercent(metrics.max_drawdown)
    );
}

/* =========================================================
   PRICE CHART
   ========================================================= */

function renderPriceChart(data) {
    const dates = data.dates || [];
    const close = data.close || [];
    const smaFast = data.sma_fast || [];
    const smaSlow = data.sma_slow || [];
    const emaFast = data.ema_fast || [];
    const emaSlow = data.ema_slow || [];

    const traces = [
        {
            x: dates,
            y: close,
            type: "scatter",
            mode: "lines",
            name: "Price",
            line: {
                width: 2
            }
        }
    ];

    if (smaFast.length) {
        traces.push({
            x: dates,
            y: smaFast,
            type: "scatter",
            mode: "lines",
            name: "SMA Fast",
            line: {
                width: 1.5,
                dash: "dot"
            }
        });
    }

    if (smaSlow.length) {
        traces.push({
            x: dates,
            y: smaSlow,
            type: "scatter",
            mode: "lines",
            name: "SMA Slow",
            line: {
                width: 1.5,
                dash: "dot"
            }
        });
    }

    if (emaFast.length) {
        traces.push({
            x: dates,
            y: emaFast,
            type: "scatter",
            mode: "lines",
            name: "EMA Fast",
            line: {
                width: 1.2
            }
        });
    }

    if (emaSlow.length) {
        traces.push({
            x: dates,
            y: emaSlow,
            type: "scatter",
            mode: "lines",
            name: "EMA Slow",
            line: {
                width: 1.2
            }
        });
    }

    renderChart(
        "price-chart",
        traces,
        {
            yaxis: {
                title: "Price"
            }
        }
    );
}

/* =========================================================
   RETURNS CHART
   ========================================================= */

function renderReturnsChart(data) {
    const dates = data.dates || [];
    const cumulative = data.cumulative_return || [];

    renderChart(
        "returns-chart",
        [
            {
                x: dates,
                y: cumulative,
                type: "scatter",
                mode: "lines",
                name: "Cumulative Return",
                fill: "tozeroy",
                line: {
                    width: 2
                }
            }
        ],
        {
            yaxis: {
                title: "Return"
            }
        }
    );
}

/* =========================================================
   DRAWDOWN CHART
   ========================================================= */

function renderDrawdownChart(data) {
    const dates = data.dates || [];
    const drawdown = data.drawdown || [];

    renderChart(
        "drawdown-chart",
        [
            {
                x: dates,
                y: drawdown,
                type: "scatter",
                mode: "lines",
                name: "Drawdown",
                fill: "tozeroy",
                line: {
                    width: 2
                }
            }
        ],
        {
            yaxis: {
                title: "Drawdown"
            }
        }
    );
}

/* =========================================================
   BACKTEST
   ========================================================= */

async function runBacktest() {
    const asset = getValue("backtest-asset", getValue("asset", "gold"));
    const strategy = getValue("strategy", "sma");
    const period = getValue("backtest-period", getValue("period", "2y"));

    const capital = safeNumber(
        getValue("capital", "100000"),
        100000
    );

    const transactionCost = safeNumber(
        getValue("transaction-cost", "0.001"),
        0.001
    );

    const fast = safeNumber(
        getValue("backtest-fast", getValue("fast", "20")),
        20
    );

    const slow = safeNumber(
        getValue("backtest-slow", getValue("slow", "50")),
        50
    );

    try {
        const params = new URLSearchParams({
            asset,
            strategy,
            period,
            capital,
            transaction_cost: transactionCost,
            fast,
            slow
        });

        const button = $("run-backtest");

        if (button) {
            button.disabled = true;
            button.textContent = "Running...";
        }

        const data = await fetchJSON(
            `${API.backtest}?${params.toString()}`
        );

        currentBacktest = data;

        updateBacktestSummary(data);
        renderBacktestChart(data);

        showToast(
            "Backtest completed successfully.",
            "success"
        );

    } catch (error) {
        console.error("Backtest error:", error);

        showToast(
            "Backtest could not be completed. Please try again after the market data is available.",
            "error"
        );

    } finally {
        const button = $("run-backtest");

        if (button) {
            button.disabled = false;
            button.textContent = "Run Backtest";
        }
    }
}

/* =========================================================
   BACKTEST SUMMARY
   ========================================================= */

function updateBacktestSummary(data) {
    const metrics = data.metrics || {};

    setText(
        "backtest-return",
        formatPercent(metrics.return)
    );

    setText(
        "backtest-sharpe",
        formatNumber(metrics.sharpe, 2)
    );

    setText(
        "backtest-drawdown",
        formatPercent(metrics.max_drawdown)
    );

    setText(
        "backtest-trades",
        formatNumber(metrics.trades, 0)
    );

    setText(
        "backtest-final-value",
        formatCurrency(metrics.final_value)
    );
}

/* =========================================================
   BACKTEST EQUITY CURVE
   ========================================================= */

function renderBacktestChart(data) {
    const dates = data.dates || [];
    const strategy = data.strategy_equity || [];
    const benchmark = data.benchmark_equity || [];

    const traces = [];

    if (strategy.length) {
        traces.push({
            x: dates,
            y: strategy,
            type: "scatter",
            mode: "lines",
            name: "Strategy",
            line: {
                width: 2.5
            }
        });
    }

    if (benchmark.length) {
        traces.push({
            x: dates,
            y: benchmark,
            type: "scatter",
            mode: "lines",
            name: "Buy & Hold",
            line: {
                width: 1.7,
                dash: "dot"
            }
        });
    }

    renderChart(
        "backtest-chart",
        traces,
        {
            yaxis: {
                title: "Portfolio Value"
            }
        }
    );
}

/* =========================================================
   CORRELATION
   ========================================================= */

async function loadCorrelation() {
    try {
        const data = await fetchJSON(API.correlation);

        renderCorrelationHeatmap(data);
        renderRollingCorrelation(data);

    } catch (error) {
        console.error("Correlation error:", error);

        showToast(
            "Correlation data is temporarily unavailable.",
            "error"
        );
    }
}

/* =========================================================
   CORRELATION HEATMAP
   ========================================================= */

function renderCorrelationHeatmap(data) {
    const matrix = data.matrix || [];
    const labels = data.labels || [];

    if (!matrix.length || !labels.length) {
        return;
    }

    renderChart(
        "correlation-chart",
        [
            {
                z: matrix,
                x: labels,
                y: labels,
                type: "heatmap",
                zmin: -1,
                zmax: 1,
                text: matrix.map(row =>
                    row.map(value => safeNumber(value).toFixed(2))
                ),
                texttemplate: "%{text}",
                hovertemplate:
                    "%{y} vs %{x}: %{z:.2f}<extra></extra>"
            }
        ],
        {
            margin: {
                l: 80,
                r: 20,
                t: 20,
                b: 60
            }
        }
    );
}

/* =========================================================
   ROLLING CORRELATION
   ========================================================= */

function renderRollingCorrelation(data) {
    const dates = data.rolling_dates || [];
    const values = data.rolling_correlation || [];

    renderChart(
        "rolling-correlation-chart",
        [
            {
                x: dates,
                y: values,
                type: "scatter",
                mode: "lines",
                name: "Rolling Correlation",
                line: {
                    width: 2
                }
            }
        ],
        {
            yaxis: {
                title: "Correlation",
                range: [-1, 1]
            }
        }
    );
}

/* =========================================================
   HEALTH CHECK
   ========================================================= */

async function checkHealth() {
    try {
        const data = await fetchJSON(API.health);

        if (data.status === "ok") {
            setStatus(true, "System online");
        } else {
            setStatus(false, "System issue");
        }

    } catch (error) {
        console.error("Health check failed:", error);

        setStatus(false, "System unavailable");
    }
}

function setStatus(online, text) {
    const statusText = $("status-text");
    const statusDot = document.querySelector(".status-dot");

    if (statusText) {
        statusText.textContent = text;
    }

    if (statusDot) {
        statusDot.classList.toggle("error", !online);
    }
}

/* =========================================================
   FORM EVENTS
   ========================================================= */

function setupEvents() {
    const analysisButton = $("run-analysis");

    if (analysisButton) {
        analysisButton.addEventListener(
            "click",
            loadAnalysis
        );
    }

    const backtestButton = $("run-backtest");

    if (backtestButton) {
        backtestButton.addEventListener(
            "click",
            runBacktest
        );
    }

    const assetSelect = $("asset");

    if (assetSelect) {
        assetSelect.addEventListener(
            "change",
            loadAnalysis
        );
    }

    const periodSelect = $("period");

    if (periodSelect) {
        periodSelect.addEventListener(
            "change",
            loadAnalysis
        );
    }

    const fastInput = $("fast");
    const slowInput = $("slow");

    if (fastInput) {
        fastInput.addEventListener("change", loadAnalysis);
    }

    if (slowInput) {
        slowInput.addEventListener("change", loadAnalysis);
    }
}

/* =========================================================
   INITIALIZATION
   ========================================================= */

async function initializeApp() {
    console.log("MarketLab initializing...");

    setupEvents();

    await checkHealth();

    /*
     * Do not fire many Yahoo Finance requests simultaneously.
     * Analysis loads first, followed by correlation and backtest.
     */
    await loadAnalysis();

    await new Promise(resolve => {
        setTimeout(resolve, 1200);
    });

    await loadCorrelation();

    await new Promise(resolve => {
        setTimeout(resolve, 1200);
    });

    await runBacktest();

    console.log("MarketLab initialized.");
}

/* =========================================================
   START APPLICATION
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    initializeApp
);
