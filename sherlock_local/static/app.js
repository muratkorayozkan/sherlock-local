"use strict";
const $ = (id) => document.getElementById(id);
let catalog = [], popular = [], selection = new Set(), job = null, timer = null, filter = "all", pollingErrors = 0;
const labels = {found: "Bulundu", absent: "Bulunamadı", unknown: "Kontrol edilemedi"};
function error(message) { $("error").textContent = message; $("error").hidden = !message; }
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {"Content-Type": "application/json", ...options.headers}});
  const data = await response.json();
  if (!response.ok) {
    let message = data.detail;
    if (Array.isArray(message)) message = "Kullanıcı adını ve platform seçimini kontrol et. 1–64 karakter: harf, rakam, alt çizgi, nokta veya tire.";
    throw new Error(message || "İstek tamamlanamadı.");
  }
  return data;
}
function updateSelection() {
  $("platform-count").textContent = selection.size;
  $("selection-note").textContent = `${selection.size} platform seçili · ${catalog.length} platform mevcut`;
  document.querySelectorAll(".preset").forEach((button) => {
    const names = button.dataset.preset === "all" ? catalog : popular;
    button.classList.toggle("selected", names.length === selection.size && names.every((name) => selection.has(name)));
  });
  $("platform-list").querySelectorAll("input").forEach((input) => { input.checked = selection.has(input.value); });
}
function buildPlatforms() {
  const fragment = document.createDocumentFragment();
  catalog.forEach((name) => {
    const label = document.createElement("label"), checkbox = document.createElement("input");
    checkbox.type = "checkbox"; checkbox.value = name;
    checkbox.addEventListener("change", () => { checkbox.checked ? selection.add(name) : selection.delete(name); updateSelection(); });
    label.append(checkbox, document.createTextNode(name)); fragment.append(label);
  });
  $("platform-list").replaceChildren(fragment); updateSelection();
}
function safeUrl(value) { try { const u = new URL(value); return ["http:", "https:"].includes(u.protocol) ? u.href : null; } catch { return null; } }
function render() {
  if (!job) return;
  const running = job.state === "running", results = job.results;
  $("username").disabled = running;
  $("search-button").disabled = running;
  $("search-button").querySelector("span:nth-child(1)").textContent = running ? "◌" : "⌕";
  $("cancel-button").hidden = !running;
  $("export-button").disabled = results.length === 0;
  $("progress-area").hidden = false;
  $("progress").max = job.total || 1; $("progress").value = results.length;
  $("progress-count").textContent = `${results.length} / ${job.total} platform`;
  $("progress-label").textContent = {running: "Platformlar kontrol ediliyor…", completed: "Arama tamamlandı", cancelled: "Arama durduruldu · tamamlanan sonuçlar korundu", failed: "Arama tamamlanamadı"}[job.state];
  $("result-subtitle").textContent = `@${job.username} için ${job.total} platformda arama${running ? " sürüyor." : "."}`;
  $("result-count").textContent = results.length;
  $("empty-state").hidden = true; $("results-toolbar").hidden = false; $("table-wrap").hidden = false;
  ["all", "found", "absent", "unknown"].forEach((status) => { $("count-" + status).textContent = status === "all" ? results.length : results.filter((r) => r.status === status).length; });
  const query = $("result-filter").value.toLocaleLowerCase("tr");
  const visible = results.filter((r) => (filter === "all" || r.status === filter) && r.site.toLocaleLowerCase("tr").includes(query));
  const fragment = document.createDocumentFragment();
  visible.forEach((r) => {
    const row = document.createElement("tr"), site = document.createElement("td"), initial = document.createElement("span");
    initial.className = "site-initial"; initial.textContent = r.site.slice(0, 1).toUpperCase(); site.append(initial, document.createTextNode(r.site));
    const state = document.createElement("td"), badge = document.createElement("span");
    badge.className = "status " + r.status; badge.textContent = labels[r.status] || labels.unknown; badge.title = r.detail || ""; state.append(badge);
    const url = safeUrl(r.url), linkCell = document.createElement("td"), action = document.createElement("td");
    if (url && r.status === "found") {
      const link = document.createElement("a"); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = r.url; linkCell.append(link);
      const arrow = link.cloneNode(false); arrow.textContent = "↗"; arrow.setAttribute("aria-label", `${r.site} profilini aç`); action.append(arrow);
    } else { linkCell.textContent = r.detail || (r.status === "absent" ? "Bu kullanıcı adı bulunamadı." : "Sonuç doğrulanamadı."); }
    const elapsed = document.createElement("td"); elapsed.textContent = typeof r.elapsed === "number" ? r.elapsed.toFixed(2) + " sn" : "—";
    row.append(site, state, linkCell, elapsed, action); fragment.append(row);
  });
  $("results-body").replaceChildren(fragment); $("no-matches").hidden = visible.length > 0;
  if (job.error) error(job.error);
}
async function poll() {
  if (!job || job.state !== "running") return;
  try {
    job = await api(`/api/searches/${job.id}`); pollingErrors = 0; error(""); render();
    if (job.state === "running") timer = setTimeout(poll, 800);
    else sessionStorage.removeItem("sherlock-active");
  } catch (e) {
    pollingErrors++; error("Arama durumu alınamadı. " + e.message);
    timer = setTimeout(poll, Math.min(1000 * 2 ** Math.min(pollingErrors, 4), 10000));
  }
}
$("search-form").addEventListener("submit", async (event) => {
  event.preventDefault(); error("");
  if (!catalog.length) return error("Platform listesi yüklenemedi. Sayfayı yenileyin.");
  if (!selection.size) return error("En az bir platform seçin.");
  $("search-button").disabled = true;
  try {
    clearTimeout(timer); filter = "all"; $("result-filter").value = "";
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("selected", b.dataset.filter === "all"));
    job = await api("/api/searches", {method:"POST", body:JSON.stringify({username:$("username").value.trim(), sites:[...selection], timeout:Number($("timeout").value)})});
    sessionStorage.setItem("sherlock-active", job.id); render(); poll();
  } catch (e) { error(e.message); $("search-button").disabled = false; }
});
$("cancel-button").addEventListener("click", async () => {
  if (!job) return;
  try { job = await api(`/api/searches/${job.id}`, {method:"DELETE"}); clearTimeout(timer); sessionStorage.removeItem("sherlock-active"); render(); } catch(e) { error(e.message); }
});
$("export-button").addEventListener("click", () => { if (job) window.location.href = `/api/searches/${job.id}/csv`; });
$("toggle-platforms").addEventListener("click", () => { const show = $("platform-picker").hidden; $("platform-picker").hidden = !show; $("toggle-platforms").setAttribute("aria-expanded", String(show)); });
$("platform-filter").addEventListener("input", () => { const q = $("platform-filter").value.toLowerCase(); $("platform-list").querySelectorAll("label").forEach((l) => { l.hidden = !l.textContent.toLowerCase().includes(q); }); });
document.querySelectorAll(".preset").forEach((button) => button.addEventListener("click", () => { selection = new Set(button.dataset.preset === "all" ? catalog : popular); updateSelection(); }));
document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => { filter = button.dataset.filter; document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("selected", b === button)); render(); }));
$("result-filter").addEventListener("input", render);
async function init() {
  try {
    const data = await api("/api/sites"); catalog = data.sites; popular = data.popular; selection = new Set(popular); buildPlatforms();
    const active = sessionStorage.getItem("sherlock-active");
    if (active) { try { job = await api(`/api/searches/${active}`); $("username").value = job.username; render(); poll(); } catch { sessionStorage.removeItem("sherlock-active"); } }
  } catch(e) { error("Platformlar yüklenemedi: " + e.message); $("search-button").disabled = true; }
}
init();
