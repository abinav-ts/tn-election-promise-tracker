const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const pct = (x, d = 0) => (x == null || isNaN(x)) ? "–" : (100 * x).toFixed(d) + "%";
const int = (n) => n == null ? "–" : Number(n).toLocaleString("en-IN");
const TERMS = {"AIADMK-2016": "AIADMK 2016–21", "DMK-2021": "DMK 2021–26", "TVK-2026": "TVK 2026–"};
const COLORS = (el = document.documentElement) => { const s = getComputedStyle(el), g = (k) => s.getPropertyValue(k).trim(); return {"AIADMK-2016": g("--c-a"), "DMK-2021": g("--c-d"), "TVK-2026": g("--c-t"), muted: g("--muted"), accent: g("--accent"), fg: g("--fg"), line: g("--line"), surface: g("--surface"), bg: g("--bg"), sg: g("--s-g"), sc: g("--s-c")}; };
const load = (f) => fetch("data/" + f).then(r => { if (!r.ok) throw new Error(f); return r.json(); });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const label = (s) => s.replace(/_/g, " ");
const monthLabel = (m) => m === 0 ? "end of term" : "month " + m;

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
  setTimeout(() => { syncThemeBtn(); const c = document.querySelector("header.site nav a[aria-current]"); if (c && c.scrollIntoView) c.scrollIntoView({inline: "center", block: "nearest"}); }, 0);
  const icon = `<svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg><svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/></svg>`;
  return `<a class="skip" href="#main">Skip to content</a><header class="site"><div class="hdr-in"><a class="brand" href="index.html">Tamil Nadu Election Promise Tracker</a><nav aria-label="Main">${links.map(l => `<a href="${l[0]}"${l[2] === page ? ' aria-current="page"' : ""}>${l[1]}</a>`).join("")}</nav><button class="theme-btn" type="button" aria-label="Switch to dark theme" aria-pressed="false">${icon}</button></div></header>`;
}
/* theme: set before first paint by the inline head script; the header button flips it and remembers the choice */
const getTheme = () => document.documentElement.dataset.theme === "dark" ? "dark" : "light";
function syncThemeBtn() { const b = document.querySelector(".theme-btn"); if (!b) return; const d = getTheme() === "dark"; b.setAttribute("aria-label", d ? "Switch to light theme" : "Switch to dark theme"); b.setAttribute("aria-pressed", String(d)); }
document.addEventListener("click", (e) => { const b = e.target.closest && e.target.closest(".theme-btn"); if (!b) return; const t = getTheme() === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = t; try { localStorage.setItem("theme", t); } catch (err) {} syncThemeBtn(); document.dispatchEvent(new Event("themechange")); });

/* motion helpers: animations play when a section is reached, and reset when it leaves, so they replay on every visit */
const REDUCED = (() => { try { return matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; } })();
function tween(el, to, dec, suffix = "%") {
  const from = el._v || 0, t0 = performance.now(), dur = 1300; el._v = to;
  if (REDUCED || from === to) { el.textContent = to.toFixed(dec) + suffix; return; }
  const step = (t) => { if (el._v !== to) return; const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); el.textContent = (from + (to - from) * e).toFixed(dec) + suffix; if (k < 1 && el._v === to) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
function onView(el, enter, leave) {
  if (!el) return;
  if (REDUCED || !window.IntersectionObserver) { setTimeout(enter, 0); return; }
  let on = false;
  new IntersectionObserver((es) => es.forEach(e => {
    if (e.isIntersecting && e.intersectionRatio >= 0.15 && !on) { on = true; enter(); }
    else if (!e.isIntersecting && on) { on = false; leave(); }
  }), {threshold: [0, 0.15], rootMargin: "0px 0px -25% 0px"}).observe(el);   // starts once the section is in the upper three quarters of the screen
}
function footer() {
  return `<footer class="site"><div class="ft-in"><p class="disc">Verdicts are made by LLMs from official documents and checked on small human samples; read the <a href="whitepaper.html">whitepaper</a> before relying on any figure.</p><p class="lic">UMC 301 Course Project 1 - Election Promise Tracking (Data Science &amp; AI), 2026. Evidence corpus snapshot 2026-10-10.<br>Code: GPL v3. Data and text: CC BY 4.0.</p></div></footer>`;
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
