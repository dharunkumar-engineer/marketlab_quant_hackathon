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

    return element
        ? element.value
        : fallback;
}


function setText(id, value) {
    const element = $(id);

    if (element) {
        element.textContent = value;
    }
}


function safeNumber(value, fallback = 0) {

    const number = Number(value);

    return Number.isFinite(number)
        ? number
        : fallback;
}


function formatNumber(value, decimals = 2) {

    const number = safeNumber(value);

    return number.toLocaleString(
        "en-US",
        {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }
    );
}


function formatPercent(value, decimals = 2) {

    const number = safeNumber(value);

    return `${number.toFixed(decimals)}%`;
}


function formatCurrency(value) {

    const number = safeNumber(value);

    return new Intl.NumberFormat(
        "en-US",
        {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 2
        }
    ).format(number);
}


/* =========================================================
   TOAST
   ========================================================= */

function showToast(message, type = "error") {

    let container =
        document.querySelector(".toast-container");

    if (!container) {

        container =
            document.createElement("div");

        container.className =
            "toast-container";

        document.body.appendChild(
            container
        );
    }

    const toast =
        document.createElement("div");

    toast.className =
        `toast ${type}`;

    toast.textContent =
        message;

    container.appendChild(
        toast
    );

    setTimeout(() => {

        toast.style.opacity = "0";

        toast.style.transform =
            "translateY(8px)";

        setTimeout(() => {
            toast.remove();
        }, 200);

    }, 4500);
}


/* =========================================================
   API REQUEST
   ========================================================= */

async function fetchJSON(url, options = {}) {

    const response =
        await fetch(
            url,
            {
                ...options,

                headers: {
                    "Accept":
                        "application/json",

                    ...(options.headers || {})
                }
            }
        );

    const contentType =
        response.headers.get(
            "content-type"
        ) || "";

    let data;

    if (
        contentType.includes(
            "application/json"
        )
    ) {

        data =
            await response.json();

    } else {

        const text =
            await response.text();

        throw new Error(
            `Server returned an unexpected response (${response.status}). ${text.slice(0, 150)}`
        );
    }

    if (!response.ok) {

        throw new Error(
            data.message ||
            data.error ||
            `Request failed with status ${response.status}`
        );
    }

    if (
        data.status &&
        data.status !== "ok"
    ) {

        throw new Error(
            data.message ||
            "API request failed."
        );
    }

    return data;
}


/* =========================================================
   PLOTLY DEFAULTS
   ========================================================= */

const plotLayout = {

    margin: {
        l: 50,
        r: 20,
        t: 20,
        b: 45
    },

    paper_bgcolor: "transparent",

    plot_bgcolor: "transparent",

    font: {
        family:
            "Inter, Arial, sans-serif",
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

function renderChart(
    elementId,
    traces,
    layout = {}
) {

    const element =
        $(elementId);

    if (!element) {

        console.warn(
            `Chart element not found: ${elementId}`
        );

        return;
    }

    if (!window.Plotly) {

        console.error(
            "Plotly is not loaded."
        );

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

        console.error(
            `Chart error: ${elementId}`,
            error
        );
    }
}


/* =========================================================
   ANALYSIS
   ========================================================= */

async function loadAnalysis() {

    const asset =
        getValue(
            "asset",
            "nvidia"
        );

    const period =
        getValue(
            "period",
            "5y"
        );

    const fast =
        getValue(
            "fast",
            "20"
        );

    const slow =
        getValue(
            "slow",
            "50"
        );


    if (
        Number(fast) < 2 ||
        Number(slow) <= Number(fast)
    ) {

        showToast(
            "Slow period must be greater than fast period.",
            "error"
        );

        return;
    }


    try {

        const params =
            new URLSearchParams({
                asset,
                period,
                fast,
                slow
            });


        const data =
            await fetchJSON(
                `${API.analysis}?${params.toString()}`
            );


        currentAnalysis =
            data;


        updateAnalysisMetrics(
            data
        );


        renderPriceChart(
            data
        );


        renderReturnsChart(
            data
        );


        renderDrawdownChart(
            data
        );


        setText(
            "assetName",
            data.asset || "—"
        );


        setText(
            "lastPrice",
            formatNumber(
                data.last_price,
                2
            )
        );


        setText(
            "lastDate",
            data.last_date || "—"
        );


        setStatus(
            true,
            "Analysis loaded"
        );


    } catch (error) {

        console.error(
            "Analysis error:",
            error
        );

        setStatus(
            false,
            "Data unavailable"
        );

        showToast(
            error.message ||
            "Analysis could not be loaded.",
            "error"
        );
    }
}


/* =========================================================
   UPDATE ANALYSIS METRICS
   ========================================================= */

function updateAnalysisMetrics(data) {

    const metrics =
        data.metrics || {};


    setText(
        "totalReturn",
        formatPercent(
            metrics.total_return
        )
    );


    setText(
        "annualReturn",
        formatPercent(
            metrics.annual_return
        )
    );


    setText(
        "volatility",
        formatPercent(
            metrics.volatility
        )
    );


    setText(
        "sharpe",
        formatNumber(
            metrics.sharpe,
            2
        )
    );


    setText(
        "drawdown",
        formatPercent(
            metrics.max_drawdown
        )
    );
}


/* =========================================================
   PRICE CHART
   ========================================================= */

function renderPriceChart(data) {

    const chart =
        data.chart || [];


    if (!chart.length) {

        return;
    }


    const dates =
        chart.map(
            item => item.date
        );


    const close =
        chart.map(
            item => item.close
        );


    const smaFast =
        chart.map(
            item => item.sma_fast
        );


    const smaSlow =
        chart.map(
            item => item.sma_slow
        );


    const emaFast =
        chart.map(
            item => item.ema_fast
        );


    const emaSlow =
        chart.map(
            item => item.ema_slow
        );


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


    if (
        smaFast.some(
            value => value !== null
        )
    ) {

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


    if (
        smaSlow.some(
            value => value !== null
        )
    ) {

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


    if (
        emaFast.some(
            value => value !== null
        )
    ) {

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


    if (
        emaSlow.some(
            value => value !== null
        )
    ) {

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
        "priceChart",
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

    const chart =
        data.chart || [];


    if (!chart.length) {

        return;
    }


    const dates =
        chart.map(
            item => item.date
        );


    const cumulative =
        chart.map(
            item => item.cumulative_return
        );


    renderChart(
        "returnChart",
        [
            {

                x: dates,

                y: cumulative,

                type: "scatter",

                mode: "lines",

                name:
                    "Cumulative Return",

                fill:
                    "tozeroy",

                line: {
                    width: 2
                }

            }
        ],
        {

            yaxis: {
                title: "Return (%)"
            }

        }
    );
}


/* =========================================================
   DRAWDOWN CHART
   ========================================================= */

function renderDrawdownChart(data) {

    const chart =
        data.chart || [];


    if (!chart.length) {

        return;
    }


    const dates =
        chart.map(
            item => item.date
        );


    const drawdown =
        chart.map(
            item => item.drawdown
        );


    renderChart(
        "drawdownChart",
        [
            {

                x: dates,

                y: drawdown,

                type: "scatter",

                mode: "lines",

                name: "Drawdown",

                fill:
                    "tozeroy",

                line: {
                    width: 2
                }

            }
        ],
        {

            yaxis: {
                title: "Drawdown (%)"
            }

        }
    );
}


/* =========================================================
   BACKTEST
   ========================================================= */

async function runBacktest() {

    const asset =
        getValue(
            "asset",
            "nvidia"
        );


    const strategy =
        getValue(
            "strategy",
            "sma"
        );


    const period =
        getValue(
            "period",
            "5y"
        );


    const capital =
        safeNumber(
            getValue(
                "capital",
                "100000"
            ),
            100000
        );


    const cost =
        safeNumber(
            getValue(
                "cost",
                "0.001"
            ),
            0.001
        );


    const fast =
        safeNumber(
            getValue(
                "fast",
                "20"
            ),
            20
        );


    const slow =
        safeNumber(
            getValue(
                "slow",
                "50"
            ),
            50
        );


    if (
        capital <= 0
    ) {

        showToast(
            "Initial capital must be greater than zero.",
            "error"
        );

        return;
    }


    if (
        cost < 0
    ) {

        showToast(
            "Transaction cost cannot be negative.",
            "error"
        );

        return;
    }


    if (
        slow <= fast
    ) {

        showToast(
            "Slow period must be greater than fast period.",
            "error"
        );

        return;
    }


    const button =
        document.querySelector(
            'button[onclick="runBacktest()"]'
        );


    try {

        if (button) {

            button.disabled = true;

            button.textContent =
                "Running...";
        }


        const params =
            new URLSearchParams({

                asset,

                strategy,

                period,

                capital,

                cost,

                fast,

                slow

            });


        const data =
            await fetchJSON(
                `${API.backtest}?${params.toString()}`
            );


        currentBacktest =
            data;


        updateBacktestSummary(
            data
        );


        renderBacktestChart(
            data
        );


        showToast(
            "Backtest completed successfully.",
            "success"
        );


    } catch (error) {

        console.error(
            "Backtest error:",
            error
        );


        showToast(
            error.message ||
            "Backtest could not be completed.",
            "error"
        );


    } finally {

        if (button) {

            button.disabled = false;

            button.textContent =
                "Run backtest";
        }
    }
}


/* =========================================================
   BACKTEST SUMMARY
   ========================================================= */

function updateBacktestSummary(data) {

    const summary =
        data.summary || {};


    setText(
        "finalValue",
        formatCurrency(
            summary.final_value
        )
    );


    setText(
        "btReturn",
        formatPercent(
            summary.return
        )
    );


    setText(
        "benchmarkReturn",
        formatPercent(
            summary.benchmark_return
        )
    );


    setText(
        "btSharpe",
        formatNumber(
            summary.sharpe,
            2
        )
    );


    setText(
        "btDrawdown",
        formatPercent(
            summary.max_drawdown
        )
    );


    setText(
        "trades",
        formatNumber(
            summary.trades,
            0
        )
    );
}


/* =========================================================
   BACKTEST EQUITY CURVE
   ========================================================= */

function renderBacktestChart(data) {

    const chart =
        data.chart || [];


    if (!chart.length) {

        return;
    }


    const dates =
        chart.map(
            item => item.date
        );


    const equity =
        chart.map(
            item => item.equity
        );


    const benchmark =
        chart.map(
            item => item.benchmark
        );


    const traces = [];


    if (
        equity.some(
            value => value !== null
        )
    ) {

        traces.push({

            x: dates,

            y: equity,

            type: "scatter",

            mode: "lines",

            name: "Strategy",

            line: {
                width: 2.5
            }

        });
    }


    if (
        benchmark.some(
            value => value !== null
        )
    ) {

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
        "equityChart",
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

        const period =
            getValue(
                "period",
                "5y"
            );


        const params =
            new URLSearchParams({
                period
            });


        const data =
            await fetchJSON(
                `${API.correlation}?${params.toString()}`
            );


        renderCorrelationHeatmap(
            data
        );


        renderRollingCorrelation(
            data
        );


    } catch (error) {

        console.error(
            "Correlation error:",
            error
        );


        showToast(
            error.message ||
            "Correlation data is temporarily unavailable.",
            "error"
        );
    }
}


/* =========================================================
   CORRELATION HEATMAP
   ========================================================= */

function renderCorrelationHeatmap(data) {

    const matrix =
        data.matrix || {};


    const labels =
        Object.keys(
            matrix
        );


    if (
        labels.length === 0
    ) {

        return;
    }


    const z =
        labels.map(
            row =>
                labels.map(
                    col =>
                        safeNumber(
                            matrix[row]?.[col],
                            0
                        )
                )
        );


    const text =
        z.map(
            row =>
                row.map(
                    value =>
                        value.toFixed(2)
                )
        );


    renderChart(
        "heatmap",
        [
            {

                z,

                x: labels,

                y: labels,

                type: "heatmap",

                zmin: -1,

                zmax: 1,

                text,

                texttemplate:
                    "%{text}",

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

    const rolling =
        data.rolling_btc_nvidia || [];


    if (
        !rolling.length
    ) {

        renderChart(
            "rollingChart",
            [],
            {
                yaxis: {
                    title: "Correlation",
                    range: [-1, 1]
                }
            }
        );

        return;
    }


    const dates =
        rolling.map(
            item => item.date
        );


    const values =
        rolling.map(
            item => item.value
        );


    renderChart(
        "rollingChart",
        [
            {

                x: dates,

                y: values,

                type: "scatter",

                mode: "lines",

                name:
                    "Bitcoin vs NVIDIA",

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

        const data =
            await fetchJSON(
                API.health
            );


        if (
            data.status === "ok"
        ) {

            setStatus(
                true,
                "System online"
            );

        } else {

            setStatus(
                false,
                "System issue"
            );
        }


    } catch (error) {

        console.error(
            "Health check failed:",
            error
        );


        setStatus(
            false,
            "System unavailable"
        );
    }
}


function setStatus(
    online,
    text
) {

    const status =
        document.querySelector(
            ".status"
        );


    if (!status) {
        return;
    }


    const dot =
        status.querySelector(
            "span"
        );


    if (dot) {

        dot.style.background =
            online
                ? ""
                : "#ef4444";
    }


    const existingText =
        Array.from(
            status.childNodes
        ).find(
            node =>
                node.nodeType ===
                Node.TEXT_NODE
        );


    if (existingText) {

        existingText.textContent =
            ` ${text}`;
    }
}


/* =========================================================
   FORM EVENTS
   ========================================================= */

function setupEvents() {

    const assetSelect =
        $("asset");


    if (assetSelect) {

        assetSelect.addEventListener(
            "change",
            loadAnalysis
        );
    }


    const periodSelect =
        $("period");


    if (periodSelect) {

        periodSelect.addEventListener(
            "change",
            async () => {

                await loadAnalysis();

                await loadCorrelation();

            }
        );
    }


    const fastInput =
        $("fast");


    if (fastInput) {

        fastInput.addEventListener(
            "change",
            loadAnalysis
        );
    }


    const slowInput =
        $("slow");


    if (slowInput) {

        slowInput.addEventListener(
            "change",
            loadAnalysis
        );
    }
}


/* =========================================================
   INITIALIZATION
   ========================================================= */

async function initializeApp() {

    console.log(
        "MarketLab initializing..."
    );


    setupEvents();


    await checkHealth();


    await loadAnalysis();


    await loadCorrelation();


    await runBacktest();


    console.log(
        "MarketLab initialized."
    );
}


/* =========================================================
   START APPLICATION
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    initializeApp
);
