const labelMap = {
  multi_vix: "Volatility Term Structure",
  credit: "Credit Risk",
  nhnl: "Breadth (NH/NL)",
  spx_vs_credit: "SPX vs Credit",
  spx_long_term: "SPX Trend",
  yield_curve: "Yield Curve"
};

const tooltipMap = {
  multi_vix: "VXST, VIX, VXV, VXMT curve shape",
  credit: "Credit spreads vs equities",
  nhnl: "New highs vs new lows breadth",
  spx_vs_credit: "Equities relative to credit risk",
  spx_long_term: "SPX vs long-term moving trend",
  yield_curve: "Slope between long and short rates"
};

const pretty = value => value.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase());

fetch("data/latest.json")
  .then(r => r.json())
  .then(d => {
    const tbody = document.querySelector("#table tbody");
    const regimeEl = document.getElementById("regime");
    const scoreEl = document.getElementById("score");
    const dateEl = document.getElementById("date");

    regimeEl.innerText = pretty(d.regime);
    regimeEl.classList.add(`regime--${d.regime}`);
    scoreEl.innerText = d.score;
    dateEl.innerText = d.date;

    Object.entries(d.signals).forEach(([key, value], index) => {
      const row = document.createElement("tr");
      row.className = "row";
      row.style.animationDelay = `${index * 60}ms`;

      const nameCell = document.createElement("td");
      nameCell.innerText = labelMap[key] || key;
      nameCell.title = tooltipMap[key] || "Signal definition";

      const statusCell = document.createElement("td");
      const status = document.createElement("span");
      status.className = `status status--${value}`;
      status.innerText = pretty(value);
      statusCell.appendChild(status);

      row.appendChild(nameCell);
      row.appendChild(statusCell);
      tbody.appendChild(row);
    });
  });
