const $ = (s, r = document) => r.querySelector(s);
const pct = (x, d = 0) => (x == null || isNaN(x)) ? "–" : (100 * x).toFixed(d) + "%";
const TERMS = {"AIADMK-2016": "AIADMK 2016–21", "DMK-2021": "DMK 2021–26", "TVK-2026": "TVK 2026–"};
const COLORS = () => { const s = getComputedStyle(document.documentElement); return {"AIADMK-2016": s.getPropertyValue("--c-a").trim(), "DMK-2021": s.getPropertyValue("--c-d").trim(), "TVK-2026": s.getPropertyValue("--c-t").trim(), muted: s.getPropertyValue("--muted").trim(), accent: s.getPropertyValue("--accent").trim(), fg: s.getPropertyValue("--fg").trim(), line: s.getPropertyValue("--line").trim()}; };
const load = (f) => fetch("data/" + f).then(r => { if (!r.ok) throw new Error(f); return r.json(); });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const label = (s) => s.replace(/_/g, " ");
const monthLabel = (m) => m === 0 ? "end of term" : "month " + m;
const SCENARIOS = [
  {key: "no_update", name: "No update", color: "muted",
   says: "TVK realises promises at the average historical pace of the two completed terms, whatever happened in its first five months.",
   weak: "Ignores the first five months entirely."},
  {key: "pace_update", name: "Scenario A: pace update (pre-specified)", color: "accent",
   says: "The average of the completed terms predicts how many promises should be realised by month 5, and TVK's relative speed since then continues.",
   weak: "The expectation uses hindsight event dates, while TVK's count is only what is documented now. Part of the apparent slowness is documentation lag, not slow delivery."},
  {key: "matched_update", name: "Scenario B: judge-matched pace update (added later)", color: "TVK-2026",
   says: "TVK's documented month-5 count is compared with the documented month-5 share of the term judged by the same judge at the same landmark (DMK 2021–26).",
   weak: "Chosen after scenario A's result was seen, and rests on one term. Its pace factor is then applied to hindsight-based hazards."}];
function nav(page) {
  const links = [["index.html", "Overview", "index"], ["promises.html", "Promise explorer", "promises"], ["whitepaper.html", "Whitepaper", "whitepaper"], ["work.html", "Work done", "work"]];
  return `<header class="site"><a class="brand" href="index.html">UMC 301 Course Project 1 - Election Promise Tracking</a><nav aria-label="Main">${links.map(l => `<a href="${l[0]}"${l[2] === page ? ' aria-current="page"' : ""}>${l[1]}</a>`).join("")}</nav></header>`;
}
function footer(sum) {
  return `<footer class="site"><p>UMC 301 Course Project 1 - Election Promise Tracking (Data Science &amp; AI), 2026. Evidence corpus snapshot 2026-10-10. Code: GPL v3. Data and text: CC BY 4.0. Verdicts are made by language models from official documents and checked on small human samples; read the <a href="whitepaper.html">whitepaper</a> before relying on any figure. ${sum ? "Verdicts file: " + esc(sum.final_export) + "." : ""}</p></footer>`;
}
function lineChart(el, datasets, opts = {}) {
  const c = COLORS();
  return new Chart(el, {type: "line", data: {datasets}, options: Object.assign({responsive: true, maintainAspectRatio: false, parsing: false,
    interaction: {mode: "nearest", intersect: false},
    scales: {x: {type: "linear", title: {display: true, text: "months since swearing-in", color: c.muted}, ticks: {color: c.muted}, grid: {color: c.line}, min: 0, max: 60},
      y: {min: 0, max: 100, title: {display: true, text: "% of promises realised", color: c.muted}, ticks: {color: c.muted, callback: v => v + "%"}, grid: {color: c.line}}},
    plugins: {legend: {labels: {color: c.fg, usePointStyle: true, boxWidth: 8}}}}, opts)});
}
