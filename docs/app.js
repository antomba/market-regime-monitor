const labelMap = {
  multi_vix: "Volatility Term Structure",
  hyg_trend: "HYG Trend",
  jnk_trend: "JNK Trend",
  nhnl: "Breadth (NH/NL)",
  spx_vs_credit: "SPX vs Credit",
  spx_long_term: "SPX Trend",
  yield_curve: "Yield Curve"
};

const tooltipMap = {
  multi_vix: "VXST, VIX, VXV, VXMT curve shape",
  hyg_trend: "HYG 20/50 EMA trend",
  jnk_trend: "JNK 20/50 EMA trend",
  nhnl: "New highs vs new lows breadth",
  spx_vs_credit: "Equities relative to credit risk",
  spx_long_term: "SPX vs long-term moving trend",
  yield_curve: "Slope between long and short rates"
};

const regimeClassMap = {
  "risk-on": "bg-emerald-400/15 text-emerald-100 border-emerald-300/40",
  "risk-off": "bg-orange-400/15 text-orange-100 border-orange-300/40"
};

const statusClassMap = {
  bullish: "bg-emerald-400/15 text-emerald-100 border-emerald-300/40",
  overperforms: "bg-emerald-400/15 text-emerald-100 border-emerald-300/40",
  normal: "bg-emerald-400/15 text-emerald-100 border-emerald-300/40",
  bearish: "bg-orange-400/15 text-orange-100 border-orange-300/40",
  underperforms: "bg-orange-400/15 text-orange-100 border-orange-300/40",
  inverted: "bg-orange-400/15 text-orange-100 border-orange-300/40",
  neutral: "bg-slate-300/10 text-slate-100 border-white/20"
};

const pretty = value => value.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase());

fetch("data/latest.json")
  .then(r => r.json())
  .then(d => {
    const tbody = document.querySelector("#table tbody");
    const regimeEl = document.getElementById("regime");
    const scoreEl = document.getElementById("score");
    const dateEl = document.getElementById("date");
    const regimeBase = regimeEl.className;

    regimeEl.innerText = pretty(d.regime);
    regimeEl.className = `${regimeBase} ${regimeClassMap[d.regime] || statusClassMap.neutral}`;
    scoreEl.innerText = d.score;
    dateEl.innerText = d.date;

    Object.entries(d.signals).forEach(([key, value], index) => {
      const row = document.createElement("tr");
      row.className = "border-b border-white/10";
      row.style.animationDelay = `${index * 60}ms`;
      row.style.animation = "fadeInUp 400ms ease both";

      const nameCell = document.createElement("td");
      nameCell.className = "py-3 pr-4 text-slate-200";
      nameCell.innerText = labelMap[key] || key;
      nameCell.title = tooltipMap[key] || "Signal definition";

      const statusCell = document.createElement("td");
      const status = document.createElement("span");
      status.className = "inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em]";
      status.innerText = pretty(value);
      status.className = `${status.className} ${statusClassMap[value] || statusClassMap.neutral}`;
      statusCell.appendChild(status);

      row.appendChild(nameCell);
      row.appendChild(statusCell);
      tbody.appendChild(row);
    });
  });
