const layoutBase = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    margin: {l: 45, r: 20, t: 10, b: 40},
    font: {family: "Inter, system-ui, sans-serif", size: 11, color: "#727780"},
    xaxis: {showgrid: false},
    yaxis: {gridcolor: "#eef0f2", zeroline: false},
    hovermode: "x unified",
    legend: {orientation: "h", y: 1.08}
};

function showError(message) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.style.display = "block";
    setTimeout(() => toast.style.display = "none", 3500);
}

function fmt(value, suffix = "") {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return `${Number(value).toLocaleString(undefined, {maximumFractionDigits: 2})}${suffix}`;
}

async function loadAnalysis() {
    try {
        const asset = document.getElementById("asset").value;
        const period = document.getElementById("period").value;
        const fast = document.getElementById("fast").value;
        const slow = document.getElementById("slow").value;

        const res = await fetch(`/api/analysis?asset=${asset}&period=${period}&fast=${fast}&slow=${slow}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Unable to load market data.");

        document.getElementById("assetName").textContent = data.asset;
        document.getElementById("lastPrice").textContent = fmt(data.last_price);
        document.getElementById("lastDate").textContent = data.last_date;
        document.getElementById("totalReturn").textContent = fmt(data.metrics.total_return, "%");
        document.getElementById("annualReturn").textContent = fmt(data.metrics.annual_return, "%");
        document.getElementById("volatility").textContent = fmt(data.metrics.volatility, "%");
        document.getElementById("sharpe").textContent = fmt(data.metrics.sharpe);
        document.getElementById("drawdown").textContent = fmt(data.metrics.max_drawdown, "%");

        const c = data.chart;
        const common = {...layoutBase};
        Plotly.react("priceChart", [
            {x: c.map(x=>x.date), y:c.map(x=>x.close), name:"Price", type:"scatter", mode:"lines"},
            {x: c.map(x=>x.date), y:c.map(x=>x.sma_fast), name:`SMA ${fast}`, type:"scatter", mode:"lines"},
            {x: c.map(x=>x.date), y:c.map(x=>x.sma_slow), name:`SMA ${slow}`, type:"scatter", mode:"lines"},
            {x: c.map(x=>x.date), y:c.map(x=>x.ema_fast), name:`EMA ${fast}`, type:"scatter", mode:"lines", visible:"legendonly"},
            {x: c.map(x=>x.date), y:c.map(x=>x.ema_slow), name:`EMA ${slow}`, type:"scatter", mode:"lines", visible:"legendonly"}
        ], {...common, height: 390, yaxis:{...common.yaxis, tickformat: ",.0f"}} , {responsive:true, displayModeBar:false});

        Plotly.react("returnChart", [
            {x:c.map(x=>x.date), y:c.map(x=>x.return), type:"bar", name:"Daily return"}
        ], {...common, height:300, yaxis:{...common.yaxis, ticksuffix:"%"}}, {responsive:true, displayModeBar:false});

        Plotly.react("drawdownChart", [
            {x:c.map(x=>x.date), y:c.map(x=>x.drawdown), type:"scatter", fill:"tozeroy", name:"Drawdown"}
        ], {...common, height:300, yaxis:{...common.yaxis, ticksuffix:"%"}}, {responsive:true, displayModeBar:false});

        loadCorrelation();
    } catch (err) {
        showError(err.message);
    }
}

async function runBacktest() {
    try {
        const params = new URLSearchParams({
            asset: document.getElementById("asset").value,
            strategy: document.getElementById("strategy").value,
            period: document.getElementById("period").value,
            capital: document.getElementById("capital").value,
            cost: document.getElementById("cost").value,
            fast: document.getElementById("fast").value,
            slow: document.getElementById("slow").value
        });
        const res = await fetch(`/api/backtest?${params}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Backtest failed.");

        const s = data.summary;
        document.getElementById("finalValue").textContent = fmt(s.final_value);
        document.getElementById("btReturn").textContent = fmt(s.return, "%");
        document.getElementById("benchmarkReturn").textContent = fmt(s.benchmark_return, "%");
        document.getElementById("btSharpe").textContent = fmt(s.sharpe);
        document.getElementById("btDrawdown").textContent = fmt(s.max_drawdown, "%");
        document.getElementById("trades").textContent = s.trades;

        const c = data.chart;
        const common = {...layoutBase};
        Plotly.react("equityChart", [
            {x:c.map(x=>x.date), y:c.map(x=>x.equity), name:data.strategy, type:"scatter", mode:"lines"},
            {x:c.map(x=>x.date), y:c.map(x=>x.benchmark), name:"Buy & Hold", type:"scatter", mode:"lines"}
        ], {...common, height:360, yaxis:{...common.yaxis, tickformat:",.0f"}}, {responsive:true, displayModeBar:false});
    } catch (err) {
        showError(err.message);
    }
}

async function loadCorrelation() {
    try {
        const period = document.getElementById("period").value;
        const res = await fetch(`/api/correlation?period=${period}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Correlation analysis failed.");

        const names = Object.keys(data.matrix);
        const z = names.map(row => names.map(col => data.matrix[row][col]));

        Plotly.react("heatmap", [{
            z, x:names, y:names, type:"heatmap", zmin:-1, zmax:1,
            text:z.map(r=>r.map(v=>v.toFixed(2))), texttemplate:"%{text}",
            hovertemplate:"%{y} × %{x}: %{z:.2f}<extra></extra>"
        }], {...layoutBase, height:330, margin:{l:80,r:20,t:20,b:60}}, {responsive:true, displayModeBar:false});

        const r = data.rolling_btc_nvidia;
        Plotly.react("rollingChart", [{
            x:r.map(x=>x.date), y:r.map(x=>x.value), type:"scatter", mode:"lines",
            name:"60-day correlation"
        }], {...layoutBase, height:330, yaxis:{...layoutBase.yaxis, range:[-1,1]}}, {responsive:true, displayModeBar:false});
    } catch (err) {
        showError(err.message);
    }
}

document.getElementById("asset").addEventListener("change", loadAnalysis);
document.getElementById("period").addEventListener("change", loadAnalysis);
loadAnalysis();
runBacktest();
