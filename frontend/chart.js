// North-Indian style kundali drawn as SVG.
// chart = { houses: [{house, sign (0-11), planets:[{abbr, deg}]}], ... }
(function () {
  const C = {   // [planet-text centre x,y, sign-number x,y, columns]
    1: [200, 92, 200, 178, 3], 2: [100, 34, 100, 80, 2], 3: [32, 100, 82, 100, 1],
    4: [100, 196, 182, 200, 3], 5: [32, 300, 82, 300, 1], 6: [100, 366, 100, 320, 2],
    7: [200, 304, 200, 224, 3], 8: [300, 366, 300, 320, 2], 9: [368, 300, 318, 300, 1],
    10: [300, 196, 218, 200, 3], 11: [368, 100, 318, 100, 1], 12: [300, 34, 300, 80, 2],
  };
  const COLORS = { Su: "#d97706", Mo: "#7c6fb0", Ma: "#e11d48", Me: "#059669", Ju: "#b45309",
    Ve: "#db2777", Sa: "#2563eb", Ra: "#7c3aed", Ke: "#c2410c", As: "#9d174d" };

  function drawChart(chart, opts = {}) {
    const ns = "http://www.w3.org/2000/svg";
    let s = `<svg viewBox="-4 -4 408 408" class="kchart" xmlns="${ns}">
      <rect x="0" y="0" width="400" height="400" class="kframe"/>
      <line x1="0" y1="0" x2="400" y2="400" class="kline"/><line x1="400" y1="0" x2="0" y2="400" class="kline"/>
      <polygon points="200,0 400,200 200,400 0,200" class="kline" fill="none"/>`;
    for (const h of chart.houses) {
      const [x, y, sx, sy, cols] = C[h.house];
      s += `<text x="${sx}" y="${sy}" class="ksign">${h.sign + 1}</text>`;
      const items = h.planets.slice();
      if (h.house === 1) items.unshift({ abbr: "As" });
      const rows = Math.ceil(items.length / cols) || 1;
      const lh = cols === 1 ? 19 : 23;
      items.forEach((p, i) => {
        const r = Math.floor(i / cols), c = i % cols;
        const inRow = Math.min(cols, items.length - r * cols);
        const px = x + (c - (inRow - 1) / 2) * (cols === 1 ? 0 : 38);
        const py = y + (r - (rows - 1) / 2) * lh + 5;
        const label = p.abbr === "As" ? "Asc" : p.abbr;
        s += `<text x="${px}" y="${py}" class="kplanet" fill="${COLORS[p.abbr] || "#9d174d"}">${label}${p.retro ? "<tspan class='kr'>R</tspan>" : ""}<title>${p.name || "Ascendant"} ${p.deg || ""}</title></text>`;
      });
    }
    s += "</svg>";
    return s;
  }
  window.drawChart = drawChart;
})();
