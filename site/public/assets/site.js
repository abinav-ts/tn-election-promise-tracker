const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const pct = (x, d = 0) => (x == null || isNaN(x)) ? "–" : (100 * x).toFixed(d) + "%";
const int = (n) => n == null ? "–" : Number(n).toLocaleString("en-IN");
const TERMS = {"AIADMK-2016": "AIADMK 2016–21", "DMK-2021": "DMK 2021–26", "TVK-2026": "TVK 2026–"};
const COLORS = (el = document.documentElement) => { const s = getComputedStyle(el), g = (k) => s.getPropertyValue(k).trim(); return {"AIADMK-2016": g("--c-a"), "DMK-2021": g("--c-d"), "TVK-2026": g("--c-t"), muted: g("--muted"), accent: g("--accent"), fg: g("--fg"), line: g("--line"), surface: g("--surface"), bg: g("--bg")}; };
const load = (f) => fetch("data/" + f).then(r => { if (!r.ok) throw new Error(f); return r.json(); });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const label = (s) => s.replace(/_/g, " ");
const monthLabel = (m) => m === 0 ? "end of term" : "month " + m;

// ?palette=blue|purple picks the colour palette and remembers it in this browser, so the tabs keep it.
try { const q = new URLSearchParams(location.search).get("palette"); if (q === "blue" || q === "purple") localStorage.setItem("palette", q); const pal = localStorage.getItem("palette"); if (pal === "blue") document.documentElement.dataset.palette = "blue"; } catch (e) {}
// ?theme=light|dark forces a theme (used for screenshots); otherwise the OS setting applies.
try { const t = new URLSearchParams(location.search).get("theme"); if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; } catch (e) {}
// Charts read their colours from CSS tokens, so redraw when the OS theme flips.
const onTheme = (fn) => { try { matchMedia("(prefers-color-scheme: dark)").addEventListener("change", fn); } catch (e) {} };

// Fill <span data-b="path" data-f="int|pct|pct1"> from a context object. If a value is missing the
// hand-written fallback text stays and the path is listed in the console (so it can be added to the exporter).
const getPath = (o, p) => p.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
function bind(ctx, root = document) {
  const miss = [];
  $$("[data-b]", root).forEach(el => {
    const v = getPath(ctx, el.dataset.b);
    if (v == null || (typeof v === "number" && isNaN(v))) { miss.push(el.dataset.b); el.classList.add("unbound"); return; }
    const f = el.dataset.f;
    el.textContent = f === "pct" ? pct(v) : f === "pct1" ? pct(v, 1) : f === "int" ? int(v) : f === "pts" ? Number(v).toFixed(1) : f === "num2" ? Number(v).toFixed(2) : v;
  });
  if (miss.length) console.info("Not yet in the exported JSON (showing fallback text):", [...new Set(miss)].join(", "));
}

const SCENARIOS = [
  {key: "no_update", name: "No update", color: "muted", dash: [6, 4],
   says: "TVK realises promises at the average historical pace of the two completed terms, whatever happened in its first five months.",
   weak: "Ignores the first five months entirely."},
  {key: "pace_update", name: "Scenario A: pace update (pre-specified)", color: "accent", dash: [],
   says: "The average of the completed terms predicts how many promises should be realised by month 5, and TVK's relative speed since then continues.",
   weak: "The expectation uses hindsight event dates, while TVK's count is only what is documented now. Part of the apparent slowness is documentation lag, not slow delivery."},
  {key: "matched_update", name: "Scenario B: judge-matched pace update (added later)", color: "TVK-2026", dash: [2, 3],
   says: "TVK's documented month-5 count is compared with the documented month-5 share of the term judged by the same judge at the same landmark (DMK 2021–26).",
   weak: "Chosen after scenario A's result was seen, and rests on one term. Its pace factor is then applied to hindsight-based hazards."}];

function nav(page) {
  const links = [["index.html", "Overview", "index"], ["promises.html", '<span class="wide">Promise explorer</span><span class="narrow">Explorer</span>', "promises"], ["whitepaper.html", "Whitepaper", "whitepaper"], ["work.html", "Work done", "work"]];
  setTimeout(() => { const c = document.querySelector("header.site nav a[aria-current]"); if (c && c.scrollIntoView) c.scrollIntoView({inline: "center", block: "nearest"}); }, 0);
  return `<a class="skip" href="#main">Skip to content</a><header class="site"><div class="hdr-in"><a class="brand" href="index.html">Tamil Nadu Election Promise Tracker</a><nav aria-label="Main">${links.map(l => `<a href="${l[0]}"${l[2] === page ? ' aria-current="page"' : ""}>${l[1]}</a>`).join("")}</nav></div></header>`;
}
function footer(sum) {
  return `<footer class="site"><p>UMC 301 Course Project 1 - Election Promise Tracking (Data Science &amp; AI), 2026. Evidence corpus snapshot 2026-10-10. Code: GPL v3. Data and text: CC BY 4.0. Verdicts are made by language models from official documents and checked on small human samples; read the <a href="whitepaper.html">whitepaper</a> before relying on any figure. ${sum ? "Verdicts file: " + esc(sum.final_export) + "." : ""}</p></footer>`;
}
function lineChart(el, datasets, opts = {}) {
  const c = COLORS(el);
  return new Chart(el, {type: "line", data: {datasets}, options: Object.assign({responsive: true, maintainAspectRatio: false, parsing: false, animation: false,
    interaction: {mode: "nearest", intersect: false},
    scales: {x: {type: "linear", title: {display: true, text: "months since swearing-in", color: c.muted}, ticks: {color: c.muted, stepSize: 12}, grid: {color: c.line}, min: 0, max: 60},
      y: {min: 0, max: 100, title: {display: true, text: "% of promises realised", color: c.muted}, ticks: {color: c.muted, callback: v => v + "%"}, grid: {color: c.line}}},
    plugins: {legend: {display: false}, tooltip: {callbacks: {label: (i) => `${i.dataset.label}: ${i.parsed.y.toFixed(0)}%`}}}}, opts)});
}
const showLoadError = (e, where = "main") => { const m = document.querySelector(where) || document.body; m.insertAdjacentHTML("afterbegin", "<p class='note'>Data failed to load: " + esc(e.message) + ". Serve the folder with a static server (for example <code>python3 -m http.server -d site/public</code>).</p>"); };
