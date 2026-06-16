const $ = (id) => document.getElementById(id);

const state = {
  apiKey: localStorage.getItem("cruel_api_key") || "",
  adminSecret: localStorage.getItem("cruel_admin_secret") || "",
  llmProvider: localStorage.getItem("cruel_llm_provider") || "auto",
  llmModel: localStorage.getItem("cruel_llm_model") || "",
};

function saveState() {
  localStorage.setItem("cruel_api_key", state.apiKey);
  localStorage.setItem("cruel_admin_secret", state.adminSecret);
  localStorage.setItem("cruel_llm_provider", state.llmProvider);
  localStorage.setItem("cruel_llm_model", state.llmModel);
}

function authHeaders() {
  const h = { "Content-Type": "application/json" };
  if (state.apiKey) h["X-API-Key"] = state.apiKey;
  return h;
}

function adminHeaders() {
  return { "Content-Type": "application/json", "X-Admin-Secret": state.adminSecret };
}

function showPage(id) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
  $(`page-${id}`).classList.add("active");
  document.querySelector(`[data-page="${id}"]`)?.classList.add("active");
  $("page-title").textContent = document.querySelector(`[data-page="${id}"] span`)?.textContent || "Dashboard";
  if (id === "dashboard") loadDashboard();
  if (id === "keys") loadKeys();
  if (id === "predictive") loadPredictiveStats();
}

async function loadHealth() {
  try {
    const r = await fetch("/health");
    const d = await r.json();
    const llmOk = d.llm?.provider !== "rule_based";
    const scraperOk = d.scraper_api_configured;
    $("sidebar-status").innerHTML = `
      <div class="status-pill"><span class="dot ok"></span> API Online</div>
      <div class="status-pill" style="margin-top:.35rem">
        <span class="dot ${llmOk ? "ok" : "warn"}"></span> LLM: ${d.llm?.provider || "—"}
      </div>
      <div class="status-pill" style="margin-top:.35rem">
        <span class="dot ${scraperOk ? "ok" : "warn"}"></span> ScraperAPI
      </div>`;
  } catch {
    $("sidebar-status").innerHTML = `<div class="status-pill"><span class="dot warn"></span> Offline</div>`;
  }
}

async function loadDashboard() {
  try {
    const r = await fetch("/api/v1/dashboard");
    const d = await r.json();
    $("stat-keys").textContent = d.active_api_keys;
    $("stat-keys-sub").textContent = `${d.total_api_keys} общо`;
    $("stat-scrapes").textContent = d.total_scrapes;
    $("stat-llm").textContent = d.llm?.provider || "rule_based";
    $("stat-llm-sub").textContent = d.llm?.nvidia_configured ? "NVIDIA ✓" : d.llm?.hf_configured ? "HF ✓" : "Fallback";
    $("stat-scraperio").textContent = d.scraperio?.strategies?.length || 0;
    $("stat-scraperio-sub").textContent = d.scraperio?.engine || "Scraper.io";

    const caps = d.scraperio;
    $("dash-capabilities").textContent = JSON.stringify(caps, null, 2);
    $("dash-llm").textContent = JSON.stringify(d.llm, null, 2);
  } catch (e) {
    console.error(e);
  }
}

function addChatMsg(text, role) {
  const div = document.createElement("div");
  div.className = `msg msg-${role}`;
  div.textContent = text;
  $("chat-messages").appendChild(div);
  $("chat-messages").scrollTop = $("chat-messages").scrollHeight;
}

async function sendChat() {
  const message = $("chat-input").value.trim();
  if (!message) return;
  addChatMsg(message, "user");
  $("chat-input").value = "";

  const endpoint = state.apiKey ? "/api/v1/chat" : "/api/v1/chat/public";
  const body = {
    message,
    execute_scrape: $("chat-execute").checked,
    json_only: $("chat-json").checked,
    llm_provider: state.llmProvider !== "auto" ? state.llmProvider : null,
    llm_model: state.llmModel || null,
  };

  try {
    const r = await fetch(endpoint, { method: "POST", headers: authHeaders(), body: JSON.stringify(body) });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Error");

    if ($("chat-json").checked) {
      $("chat-json-out").textContent = JSON.stringify(d, null, 2);
      addChatMsg("JSON отговор (виж панела)", "bot");
    } else {
      addChatMsg(d.reply || d.command?.explanation || "OK", "bot");
      $("chat-json-out").textContent = JSON.stringify(d.command, null, 2);
    }
  } catch (e) {
    addChatMsg("Грешка: " + e.message, "bot");
  }
}

async function runQuickScrape() {
  if (!state.apiKey) return alert("Въведете API ключ в Settings");
  const url = $("quick-url").value.trim();
  const extract = $("quick-extract").value.split(",").map((s) => s.trim()).filter(Boolean);
  try {
    const r = await fetch("/api/v1/scrape", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ url, extract }),
    });
    const d = await r.json();
    $("quick-result").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("quick-result").textContent = "Error: " + e.message;
  }
}

async function runUniversalScrape() {
  if (!state.apiKey) return alert("Въведете API ключ в Settings");
  const url = $("univ-url").value.trim();
  const maxItems = parseInt($("univ-max").value, 10) || 15;
  try {
    $("univ-result").textContent = "Scraping... (може да отнеме време)";
    const r = await fetch("/api/v1/scrape/universal", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ url, max_items: maxItems, production_mode: true }),
    });
    const d = await r.json();
    $("univ-result").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("univ-result").textContent = "Error: " + e.message;
  }
}

async function createKey() {
  if (!state.adminSecret) return alert("Въведете Admin Secret в Settings");
  try {
    const r = await fetch("/admin/keys", {
      method: "POST", headers: adminHeaders(),
      body: JSON.stringify({ name: $("key-name").value || "default" }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail);
    $("new-key-alert").classList.remove("hidden");
    $("new-key-value").textContent = d.key;
    state.apiKey = d.key;
    saveState();
    $("set-api-key").value = d.key;
    loadKeys();
    loadDashboard();
  } catch (e) {
    alert("Грешка: " + e.message);
  }
}

async function loadKeys() {
  if (!state.adminSecret) return;
  try {
    const r = await fetch("/admin/keys", { headers: adminHeaders() });
    const keys = await r.json();
    if (!r.ok) return;
    const tbody = $("keys-tbody");
    tbody.innerHTML = keys.map((k) => `
      <tr>
        <td><strong>${k.name}</strong><br><small style="color:var(--muted)">${k.key_prefix}</small></td>
        <td>${k.usage_count}</td>
        <td>${k.is_active ? '<span class="badge badge-green">active</span>' : '<span class="badge badge-red">revoked</span>'}</td>
        <td>${new Date(k.created_at).toLocaleDateString()}</td>
        <td>${k.is_active ? `<button class="btn btn-danger btn-sm" onclick="revokeKey('${k.id}')">Revoke</button>` : "—"}</td>
      </tr>`).join("");
  } catch {}
}

async function revokeKey(id) {
  await fetch(`/admin/keys/${id}`, { method: "DELETE", headers: adminHeaders() });
  loadKeys();
}

function saveSettings() {
  state.apiKey = $("set-api-key").value.trim();
  state.adminSecret = $("set-admin-secret").value.trim();
  state.llmProvider = $("set-llm-provider").value;
  state.llmModel = $("set-llm-model").value.trim();
  saveState();
  $("settings-saved").classList.remove("hidden");
  setTimeout(() => $("settings-saved").classList.add("hidden"), 2500);
  loadHealth();
}

async function populateModels() {
  try {
    const r = await fetch("/api/v1/llm/status");
    const d = await r.json();
    const sel = $("set-llm-model");
    sel.innerHTML = '<option value="">— default —</option>';
    const prov = state.llmProvider === "huggingface" ? "hf" : state.llmProvider === "groq" ? "groq" : state.llmProvider === "ollama" ? "ollama" : "nvidia";
    const models = prov === "groq" ? d.groq_models : prov === "hf" ? d.hf_models : prov === "ollama" ? d.ollama_models : d.nvidia_models;
    (models || []).forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.name + (m.free ? " (free)" : "") + (m.speed ? ` · ${m.speed}` : "");
      sel.appendChild(opt);
    });
    if (state.llmModel) sel.value = state.llmModel;
  } catch {}
}

function addAgentThought(phase, text) {
  const div = document.createElement("div");
  div.className = "msg msg-bot";
  div.textContent = `[${phase}] ${text}`;
  $("agent-thoughts").appendChild(div);
  $("agent-thoughts").scrollTop = $("agent-thoughts").scrollHeight;
}

async function runAgent() {
  if (!state.apiKey) return alert("Въведете API ключ в Settings");
  const goal = $("agent-goal").value.trim();
  if (!goal) return;
  $("agent-thoughts").innerHTML = "";
  addAgentThought("start", goal);
  try {
    const r = await fetch("/api/v1/agent/research", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({
        goal, use_wayback: $("agent-wayback").checked,
        llm_provider: state.llmProvider !== "auto" ? state.llmProvider : null,
        llm_model: state.llmModel || null,
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Error");
    if (d.status === "clarification_needed") {
      addAgentThought("clarify", d.question);
      return;
    }
    $("agent-result").textContent = d.synthesis || JSON.stringify(d, null, 2);
    addAgentThought("done", `Намерени ${d.sources_found} източника, прочетени ${d.sources_scraped}.`);
  } catch (e) {
    addAgentThought("error", e.message);
  }
}

function runAgentStream() {
  if (!state.apiKey) return alert("Въведете API ключ в Settings");
  const goal = $("agent-goal").value.trim();
  if (!goal) return;
  $("agent-thoughts").innerHTML = "";
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws/agent`);
  ws.onopen = () => {
    ws.send(JSON.stringify({
      goal, api_key: state.apiKey,
      llm_provider: state.llmProvider !== "auto" ? state.llmProvider : null,
      llm_model: state.llmModel || null,
    }));
  };
  ws.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.type === "thought") addAgentThought(d.phase, d.text);
    if (d.type === "result") $("agent-result").textContent = d.data?.synthesis || JSON.stringify(d.data, null, 2);
    if (d.type === "synthesis_token") $("agent-result").textContent += d.text;
    if (d.type === "done") addAgentThought("done", "Готово!");
    if (d.type === "error") addAgentThought("error", d.text);
  };
  ws.onerror = () => addAgentThought("error", "WebSocket грешка");
}

async function runVisionScrape() {
  if (!state.apiKey) return alert("Въведете API ключ в Settings");
  const url = $("vision-url").value.trim();
  const goal = $("vision-goal").value.trim();
  if (!url) return;
  $("vision-result").textContent = "Vision scraping...";
  try {
    const r = await fetch("/api/v1/scrape/vision", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ url, goal }),
    });
    const d = await r.json();
    $("vision-result").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("vision-result").textContent = "Error: " + e.message;
  }
}

async function loadPredictiveStats() {
  if (!state.apiKey) return;
  try {
    const r = await fetch("/api/v1/predictive/stats", { headers: authHeaders() });
    const d = await r.json();
    $("predictive-stats").textContent = `Контекст теми: ${d.context_topics} · Кеширани: ${d.cached_items}`;
  } catch {}
}

async function savePredictiveContext() {
  if (!state.apiKey) return alert("Въведете API ключ");
  const message = $("predictive-context").value.trim();
  if (!message) return;
  await fetch("/api/v1/predictive/context", {
    method: "POST", headers: authHeaders(),
    body: JSON.stringify({ message }),
  });
  loadPredictiveStats();
  alert("Контекстът е записан — бекграунд scrape ще стартира автоматично.");
}

async function runPredictiveCycle() {
  if (!state.apiKey) return alert("Въведете API ключ");
  $("predictive-stats").textContent = "Стартирам predictive цикъл...";
  const r = await fetch("/api/v1/predictive/run", { method: "POST", headers: authHeaders() });
  const d = await r.json();
  $("predictive-stats").textContent = `Готово: ${d.topics_processed} теми, ${d.items_cached} кеширани`;
  loadPredictiveSuggestions();
}

async function loadPredictiveSuggestions() {
  if (!state.apiKey) return;
  const ctx = $("predictive-context").value.trim();
  const r = await fetch(`/api/v1/predictive/suggestions?message=${encodeURIComponent(ctx)}`, { headers: authHeaders() });
  const d = await r.json();
  const box = $("predictive-suggestions");
  box.innerHTML = "";
  if (!d.suggestions?.length) {
    box.innerHTML = '<div class="msg msg-sys">Няма кеширани материали още.</div>';
    return;
  }
  d.suggestions.forEach((group) => {
    const h = document.createElement("div");
    h.className = "msg msg-sys";
    h.textContent = `📂 ${group.topic}`;
    box.appendChild(h);
    (group.items || []).forEach((item) => {
      const m = document.createElement("div");
      m.className = "msg msg-bot";
      m.textContent = `${item.title}\n${item.url}\n${item.content_preview}`;
      box.appendChild(m);
    });
  });
}

function init() {
  $("set-api-key").value = state.apiKey;
  $("set-admin-secret").value = state.adminSecret;
  $("set-llm-provider").value = state.llmProvider;

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.page));
  });

  $("btn-send-chat").addEventListener("click", sendChat);
  $("chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  $("btn-quick-scrape").addEventListener("click", runQuickScrape);
  $("btn-univ-scrape").addEventListener("click", runUniversalScrape);
  $("btn-create-key").addEventListener("click", createKey);
  $("btn-save-settings").addEventListener("click", saveSettings);
  $("btn-agent-run").addEventListener("click", runAgent);
  $("btn-agent-stream").addEventListener("click", runAgentStream);
  $("btn-vision-scrape").addEventListener("click", runVisionScrape);
  $("btn-predictive-save").addEventListener("click", savePredictiveContext);
  $("btn-predictive-run").addEventListener("click", runPredictiveCycle);
  $("btn-predictive-load").addEventListener("click", loadPredictiveSuggestions);
  $("set-llm-provider").addEventListener("change", () => { populateModels(); });

  document.querySelectorAll(".chip[data-agent]").forEach((el) => {
    el.addEventListener("click", () => { $("agent-goal").value = el.dataset.agent; });
  });

  document.querySelectorAll(".chip").forEach((el) => {
    el.addEventListener("click", () => { $("chat-input").value = el.dataset.msg; });
  });

  populateModels();
  loadHealth();
  loadDashboard();
  showPage("dashboard");
}

window.revokeKey = revokeKey;
document.addEventListener("DOMContentLoaded", init);
