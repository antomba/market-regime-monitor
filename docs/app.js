fetch("../data/latest.json")
  .then(r => r.json())
  .then(d => {
    const t = document.getElementById("table");
    Object.entries(d.signals).forEach(([k,v]) => {
      const row = t.insertRow();
      row.insertCell().innerText = k;
      const c = row.insertCell();
      c.innerText = v;
      c.className = v;
    });
  });