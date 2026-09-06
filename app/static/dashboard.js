const $ = (id) => document.getElementById(id);

const I18N = {
  en: {
    nav_research: "Research",
    nav_extract: "Extract",
    nav_intel: "Intelligence",
    nav_system: "System",
    nav_dashboard: "Dashboard",
    nav_chat: "LLM Chat",
    nav_keys: "API Keys",
    nav_settings: "Settings",
    hero_title: "What do you need to know?",
    hero_sub: "Research, extract, or scan — Copilot picks the tools. Discoverable in one prompt.",
    need_key: "Save an API key in Settings first.",
  },
  bg: {
    nav_research: "Изследване",
    nav_extract: "Извличане",
    nav_intel: "Разузнаване",
    nav_system: "Система",
    nav_dashboard: "Табло",
    nav_chat: "LLM чат",
    nav_keys: "API ключове",
    nav_settings: "Настройки",
    hero_title: "Какво трябва да научите?",
    hero_sub: "Проучване, извличане или сканиране — Copilot избира инструментите.",
    need_key: "Запазете API ключ в Настройки.",
  },
};

const PAGES = [
  { id: "dashboard", label: "Dashboard" },
  { id: "agent", label: "Argos Agent" },
  { id: "detective", label: "Smart Detective" },
  { id: "chat", label: "LLM Chat" },
  { id: "quick", label: "Quick Scrape" },
  { id: "universal", label: "Universal Scrape" },
  { id: "vision", label: "Vision Scrape" },
  { id: "predictive", label: "Predictive" },
  { id: "compliance", label: "Privacy Layers" },
  { id: "probe", label: "Active Probe" },
  { id: "tiktok", label: "TikTok" },
  { id: "inbox", label: "Inbox" },
  { id: "stockargos", label: "StockArgos" },
  { id: "keys", label: "API Keys" },
  { id: "settings", label: "Settings" },
];

const state = {
  apiKey: localStorage.getItem("cruel_api_key") || "",
  adminSecret: localStorage.getItem("cruel_admin_secret") || "",
  llmProvider: localStorage.getItem("cruel_llm_provider") || "auto",
  llmModel: localStorage.getItem("cruel_llm_model") || "",
  privacyLayer: localStorage.getItem("cruel_privacy_layer") || "",
  country: localStorage.getItem("cruel_country") || "DE",
  theme: localStorage.getItem("argos_theme") || "dark",
  locale: localStorage.getItem("argos_locale") || "auto",
  reducedMotion: localStorage.getItem("argos_reduced_motion") === "true",
  copilotDock: localStorage.getItem("argos_copilot_dock") !== "false",
};

function resolvedLocale() {
  if (state.locale === "bg" || state.locale === "en") return state.locale;
  return navigator.language?.startsWith("bg") ? "bg" : "en";
}

function t(key) {
  return (I18N[resolvedLocale()] || I18N.en)[key] || key;
}

function saveState() {
  localStorage.setItem("cruel_api_key", state.apiKey);
  localStorage.setItem("cruel_admin_secret", state.adminSecret);
  localStorage.setItem("cruel_llm_provider", state.llmProvider);
  localStorage.setItem("cruel_llm_model", state.llmModel);
  localStorage.setItem("cruel_privacy_layer", state.privacyLayer);
  localStorage.setItem("cruel_country", state.country);
  localStorage.setItem("argos_theme", state.theme);
  localStorage.setItem("argos_locale", state.locale);
  localStorage.setItem("argos_reduced_motion", String(state.reducedMotion));
  localStorage.setItem("argos_copilot_dock", String(state.copilotDock));
}

function applyChrome() {
  document.documentElement.dataset.theme = state.theme;
  document.documentElement.dataset.reducedMotion = String(state.reducedMotion);
  document.body.classList.toggle("copilot-open", state.copilotDock);
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  const locBtn = $("btn-locale");
  if (locBtn) locBtn.textContent = resolvedLocale().toUpperCase();
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
  const page = $(`page-${id}`);
  if (!page) return;
  page.classList.add("active");
  document.querySelector(`[data-page="${id}"]`)?.classList.add("active");
  const label = document.querySelector(`[data-page="${id}"] span:last-child`)?.textContent;
  $("page-title").textContent = label || "Dashboard";
  if (id === "dashboard") loadDashboard();
  if (id === "keys") loadKeys();
  if (id === "predictive") loadPredictiveStats();
  if (id === "probe") loadProbeCapabilities();
  if (id === "inbox") loadInboxData();
  if (id === "stockargos") loadStockArgosSignals();
  if (id === "compliance") loadComplianceLayers();
  if (id === "detective" && $("det-country")) $("det-country").value = state.country;
}

async function loadHealth() {
  try {
    const r = await fetch("/health");
    const d = await r.json();
    const llmOk = d.llm?.provider !== "rule_based";
    const scraperOk = d.scraper_api_configured;
    const insecure = d.security?.admin_secret_insecure;
    $("sidebar-status").innerHTML = `
      <div class="status-pill"><span class="dot ok"></span> API ${d.version || ""}</div>
      <div class="status-pill" style="margin-top:.35rem">
        <span class="dot ${llmOk ? "ok" : "warn"}"></span> LLM: ${d.llm?.provider || "—"}
      </div>
      <div class="status-pill" style="margin-top:.35rem">
        <span class="dot ${scraperOk ? "ok" : "warn"}"></span> ScraperAPI
      </div>
      ${insecure ? `<div class="status-pill" style="margin-top:.35rem"><span class="dot warn"></span> Default admin secret</div>` : ""}`;
  } catch {
    $("sidebar-status").innerHTML = `<div class="status-pill"><span class="dot warn"></span> Offline</div>`;
  }
}

function renderSuggestions(items) {
  const box = $("dash-suggestions");
  if (!box) return;
  if (!items?.length) {
    box.innerHTML = '<div class="msg msg-sys">No recommendations — system looks healthy.</div>';
    return;
  }
  box.innerHTML = items.map((s) => `
    <div class="suggestion-item sev-${s.severity || "info"}" data-action="${s.action || ""}">
      <strong>${s.title}</strong>
      <span>${s.detail || ""}</span>
    </div>`).join("");
  box.querySelectorAll(".suggestion-item").forEach((el) => {
    el.addEventListener("click", () => handleSuggestion(el.dataset.action));
  });
}

function handleSuggestion(action) {
  if (action === "open_settings") return showPage("settings");
  if (action === "open_detective") return showPage("detective");
  if (action === "open_agent") return showPage("agent");
  if (action === "focus_command") {
    state.copilotDock = true;
    applyChrome();
    $("hero-input")?.focus();
  }
}

function renderActivity(rows) {
  const box = $("dash-activity");
  if (!box) return;
  if (!rows?.length) {
    box.innerHTML = '<div class="msg msg-sys">No jobs yet. Ask Copilot a question.</div>';
    return;
  }
  box.innerHTML = rows.map((row) => `
    <div class="activity-item">
      ${row.success ? "✓" : "✗"} <strong>${row.mode}</strong> · ${(row.url || "").slice(0, 72)}
    </div>`).join("");
}

async function loadDashboard() {
  try {
    const r = await fetch("/api/v1/dashboard");
    const d = await r.json();
    $("stat-keys").textContent = d.active_api_keys;
    $("stat-keys-sub").textContent = `${d.total_api_keys} total`;
    $("stat-scrapes").textContent = d.total_scrapes;
    $("stat-llm").textContent = d.llm?.provider || "rule_based";
    $("stat-llm-sub").textContent = d.llm?.groq_configured ? "Groq ✓" : d.llm?.nvidia_configured ? "NVIDIA ✓" : d.llm?.hf_configured ? "HF ✓" : "Fallback";
    $("stat-scraperio").textContent = d.scraperio?.strategies?.length || 0;
    $("stat-scraperio-sub").textContent = d.scraperio?.engine || "Scraper.io";
    $("dash-capabilities").textContent = JSON.stringify(d.scraperio, null, 2);
    $("dash-llm").textContent = JSON.stringify(d.llm, null, 2);
  } catch (e) {
    console.error(e);
  }
  if (!state.apiKey) return;
  try {
    const [s, a] = await Promise.all([
      fetch("/api/v1/copilot/suggestions", { headers: authHeaders() }),
      fetch("/api/v1/observability/activity?limit=8", { headers: authHeaders() }),
    ]);
    if (s.ok) {
      const data = await s.json();
      renderSuggestions(data.suggestions);
    }
    if (a.ok) {
      const data = await a.json();
      renderActivity(data.activity);
    }
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

function addCopilotMsg(text, role) {
  const div = document.createElement("div");
  div.className = `msg msg-${role}`;
  div.textContent = text;
  $("copilot-messages").appendChild(div);
  $("copilot-messages").scrollTop = $("copilot-messages").scrollHeight;
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
      addChatMsg("JSON response (see panel)", "bot");
    } else {
      addChatMsg(d.reply || d.command?.explanation || "OK", "bot");
      $("chat-json-out").textContent = JSON.stringify(d.command, null, 2);
    }
  } catch (e) {
    addChatMsg("Error: " + e.message, "bot");
  }
}

async function runCopilot(message, { fromHero } = {}) {
  const text = (message || "").trim();
  if (!text) return;
  if (!state.apiKey) {
    alert(t("need_key"));
    showPage("settings");
    return;
  }
  state.copilotDock = true;
  applyChrome();
  addCopilotMsg(text, "user");
  addCopilotMsg("Working…", "sys");
  try {
    const r = await fetch("/api/v1/copilot", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        message: text,
        execute: true,
        llm_provider: state.llmProvider !== "auto" ? state.llmProvider : null,
        llm_model: state.llmModel || null,
        privacy_layer: state.privacyLayer || null,
        country: state.country || null,
      }),
    });
    const d = await r.json();
    const sys = [...$("copilot-messages").querySelectorAll(".msg-sys")].pop();
    if (sys && sys.textContent === "Working…") sys.remove();
    if (!r.ok) throw new Error(d.detail || "Copilot failed");
    (d.steps || []).forEach((step) => {
      const chip = document.createElement("div");
      chip.className = "step-chip";
      chip.textContent = `${step.ok ? "✓" : "✗"} ${step.tool}${step.error ? " — " + step.error : ""}`;
      $("copilot-messages").appendChild(chip);
    });
    addCopilotMsg(d.reply || "Done.", "bot");
    if (fromHero) loadDashboard();
  } catch (e) {
    addCopilotMsg("Error: " + e.message, "bot");
  }
}

async function runQuickScrape() {
  if (!state.apiKey) return alert(t("need_key"));
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
  if (!state.apiKey) return alert(t("need_key"));
  const url = $("univ-url").value.trim();
  const maxItems = parseInt($("univ-max").value, 10) || 15;
  try {
    $("univ-result").textContent = "Scraping...";
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
  if (!state.adminSecret) return alert("Enter Admin Secret in Settings");
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
    alert("Error: " + e.message);
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

async function saveSettings() {
  state.apiKey = $("set-api-key").value.trim();
  state.adminSecret = $("set-admin-secret").value.trim();
  state.llmProvider = $("set-llm-provider").value;
  state.llmModel = $("set-llm-model").value.trim();
  state.theme = $("set-theme").value;
  state.locale = $("set-locale").value;
  state.privacyLayer = $("set-privacy-layer").value;
  state.country = ($("set-country").value || "DE").toUpperCase();
  state.reducedMotion = $("set-reduced-motion").checked;
  state.copilotDock = $("set-copilot-dock").checked;
  saveState();
  applyChrome();
  if (state.apiKey) {
    try {
      await fetch("/api/v1/preferences", {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify({
          theme: state.theme,
          locale: state.locale,
          privacy_layer: state.privacyLayer,
          country: state.country,
          llm_provider: state.llmProvider,
          llm_model: state.llmModel,
          reduced_motion: state.reducedMotion,
          copilot_dock_open: state.copilotDock,
        }),
      });
    } catch {}
  }
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
  if (!state.apiKey) return alert(t("need_key"));
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
        privacy_layer: state.privacyLayer || null,
        country: state.country || null,
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Error");
    if (d.status === "clarification_needed") {
      addAgentThought("clarify", d.question);
      return;
    }
    $("agent-result").textContent = d.synthesis || JSON.stringify(d, null, 2);
    addAgentThought("done", `Found ${d.sources_found} sources, read ${d.sources_scraped}.`);
  } catch (e) {
    addAgentThought("error", e.message);
  }
}

function runAgentStream() {
  if (!state.apiKey) return alert(t("need_key"));
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
    if (d.type === "done") addAgentThought("done", "Done");
    if (d.type === "error") addAgentThought("error", d.text);
  };
  ws.onerror = () => addAgentThought("error", "WebSocket error");
}

async function runVisionScrape() {
  if (!state.apiKey) return alert(t("need_key"));
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
    $("predictive-stats").textContent = `Topics: ${d.context_topics} · Cached: ${d.cached_items}`;
  } catch {}
}

async function savePredictiveContext() {
  if (!state.apiKey) return alert(t("need_key"));
  const message = $("predictive-context").value.trim();
  if (!message) return;
  await fetch("/api/v1/predictive/context", {
    method: "POST", headers: authHeaders(),
    body: JSON.stringify({ message }),
  });
  loadPredictiveStats();
}

async function runPredictiveCycle() {
  if (!state.apiKey) return alert(t("need_key"));
  $("predictive-stats").textContent = "Running predictive cycle...";
  const r = await fetch("/api/v1/predictive/run", { method: "POST", headers: authHeaders() });
  const d = await r.json();
  $("predictive-stats").textContent = `Done: ${d.topics_processed} topics, ${d.items_cached} cached`;
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
    box.innerHTML = '<div class="msg msg-sys">No cached materials yet.</div>';
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

function getSelectedProbeModes() {
  return [...document.querySelectorAll(".probe-mode.active")].map((el) => el.dataset.mode);
}

async function loadProbeCapabilities() {
  try {
    const r = await fetch("/api/v1/probe/capabilities");
    const d = await r.json();
    const backend = d.pheromones?.backend || "sqlite";
    $("probe-backend").textContent = `Pheromone backend: ${backend} (Redis: ${d.pheromones?.redis_url_configured ? "configured" : "not set"})`;
    $("probe-result").textContent = JSON.stringify(d, null, 2);
  } catch {}
}

async function runProbe() {
  if (!state.apiKey) return alert(t("need_key"));
  const url = $("probe-url").value.trim();
  if (!url) return;
  const modes = getSelectedProbeModes();
  if (!modes.length) return alert("Select at least one mode");
  const dryRun = $("probe-dry-run").checked;
  const authorized = $("probe-authorized")?.checked;
  if (!dryRun && !authorized) return alert("Live probe requires the authorized-target confirmation.");
  $("probe-result").textContent = "Active Probe running...";
  try {
    const r = await fetch("/api/v1/probe/run", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({
        url, modes,
        goal: $("probe-goal").value.trim(),
        dry_run: dryRun,
        authorized_target: Boolean(authorized),
        emit_stockargos: $("probe-stockargos").checked,
        llm_provider: state.llmProvider !== "auto" ? state.llmProvider : null,
        privacy_layer: state.privacyLayer || null,
        country: state.country || null,
      }),
    });
    const d = await r.json();
    $("probe-result").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("probe-result").textContent = "Error: " + e.message;
  }
}

async function loadPheromones() {
  if (!state.apiKey) return alert(t("need_key"));
  const r = await fetch("/api/v1/probe/pheromones", { headers: authHeaders() });
  const d = await r.json();
  $("probe-result").textContent = JSON.stringify(d, null, 2);
}

async function runTikTokAnalyze() {
  if (!state.apiKey) return alert(t("need_key"));
  const url = $("tiktok-url").value.trim();
  if (!url) return;
  $("tiktok-result").textContent = "Analyzing TikTok...";
  try {
    const r = await fetch("/api/v1/multimodal/tiktok", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({
        url,
        llm_provider: state.llmProvider !== "auto" ? state.llmProvider : null,
      }),
    });
    const d = await r.json();
    $("tiktok-result").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("tiktok-result").textContent = "Error: " + e.message;
  }
}

async function loadInboxData() {
  if (!state.apiKey) return;
  try {
    const [statusR, subR] = await Promise.all([
      fetch("/api/v1/inbox/status", { headers: authHeaders() }),
      fetch("/api/v1/inbox/submissions?limit=10", { headers: authHeaders() }),
    ]);
    const status = await statusR.json();
    const subs = await subR.json();
    $("inbox-status").textContent = status.enabled
      ? `Enabled · Pending: ${status.pending_submissions} · Replied: ${status.replied_submissions} · Messages: ${status.total_messages}`
      : `Disabled — configure IMAP_* and INBOX_ENABLED=true`;
    $("inbox-data").textContent = JSON.stringify({ status, submissions: subs.submissions }, null, 2);
  } catch (e) {
    $("inbox-data").textContent = "Error: " + e.message;
  }
}

async function pollInbox() {
  if (!state.apiKey) return alert(t("need_key"));
  $("inbox-status").textContent = "Polling inbox...";
  const r = await fetch("/api/v1/inbox/poll", { method: "POST", headers: authHeaders() });
  const d = await r.json();
  $("inbox-status").textContent = JSON.stringify(d);
  loadInboxData();
}

async function emitStockArgosSignal() {
  if (!state.apiKey) return alert(t("need_key"));
  const title = $("sa-title").value.trim();
  const content = $("sa-content").value.trim();
  if (!title || !content) return alert("Title and content are required");
  $("sa-result").textContent = "Emitting signal...";
  const r = await fetch("/api/v1/integrations/stockargos/signal", {
    method: "POST", headers: authHeaders(),
    body: JSON.stringify({
      signal_type: $("sa-type").value.trim() || "manual",
      title, content,
      source_url: $("sa-url").value.trim(),
    }),
  });
  const d = await r.json();
  $("sa-result").textContent = JSON.stringify(d, null, 2);
}

async function loadStockArgosSignals() {
  if (!state.apiKey) return;
  try {
    const r = await fetch("/api/v1/integrations/stockargos/signals?limit=15", { headers: authHeaders() });
    const d = await r.json();
    $("sa-result").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("sa-result").textContent = "Error: " + e.message;
  }
}

async function loadComplianceLayers() {
  try {
    const r = await fetch("/api/v1/compliance/layers");
    const d = await r.json();
    $("compliance-layers").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("compliance-layers").textContent = "Error: " + e.message;
  }
}

async function runDetective() {
  if (!state.apiKey) return alert(t("need_key"));
  const url = $("det-url").value.trim();
  if (!url) return;
  $("detective-result").textContent = "Smart Detective running...";
  const body = {
    url,
    goal: $("det-goal").value.trim(),
    passive_only: $("det-passive").checked,
    llm_provider: state.llmProvider !== "auto" ? state.llmProvider : null,
  };
  const layer = $("det-layer").value;
  const country = $("det-country").value.trim();
  if (layer) body.privacy_layer = layer;
  if (country) body.country = country.toUpperCase();
  try {
    const r = await fetch("/api/v1/intelligence/detective", {
      method: "POST", headers: authHeaders(), body: JSON.stringify(body),
    });
    const d = await r.json();
    $("detective-result").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("detective-result").textContent = "Error: " + e.message;
  }
}

async function runOsint() {
  if (!state.apiKey) return alert(t("need_key"));
  $("detective-result").textContent = "OSINT investigating...";
  const body = {
    name: $("osint-name").value.trim(),
    url: $("osint-url").value.trim(),
    tiktok_url: $("osint-tiktok").value.trim(),
    country: ($("osint-country").value || "DE").toUpperCase(),
    privacy_layer: $("det-layer").value || null,
    llm_provider: state.llmProvider !== "auto" ? state.llmProvider : null,
  };
  try {
    const r = await fetch("/api/v1/osint/investigate", {
      method: "POST", headers: authHeaders(), body: JSON.stringify(body),
    });
    const d = await r.json();
    $("detective-result").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("detective-result").textContent = "Error: " + e.message;
  }
}

async function runGdprScan() {
  if (!state.apiKey) return alert(t("need_key"));
  const text = $("gdpr-text").value.trim();
  if (!text) return;
  const r = await fetch("/api/v1/compliance/gdpr-scan", {
    method: "POST", headers: authHeaders(),
    body: JSON.stringify({ text, privacy_layer: $("gdpr-layer").value }),
  });
  const d = await r.json();
  $("gdpr-result").textContent = JSON.stringify(d, null, 2);
}

function paletteItems(query) {
  const q = query.toLowerCase();
  const actions = [
    { id: "act-copilot", label: "Ask Copilot", run: () => { closePalette(); $("copilot-input").focus(); state.copilotDock = true; applyChrome(); } },
    { id: "act-health", label: "Inspect health", run: () => { closePalette(); runCopilot("Inspect system health"); } },
    { id: "act-anomalies", label: "Spot anomalies", run: () => { closePalette(); runCopilot("What is failing?"); } },
  ];
  return [
    ...PAGES.map((p) => ({ id: p.id, label: `Go to ${p.label}`, run: () => { closePalette(); showPage(p.id); } })),
    ...actions,
  ].filter((item) => item.label.toLowerCase().includes(q));
}

function renderPalette(query) {
  const items = paletteItems(query);
  $("palette-list").innerHTML = items.map((item, i) => `
    <button class="palette-item${i === 0 ? " active" : ""}" data-id="${item.id}" type="button">${item.label}</button>
  `).join("") || `<div class="palette-item">No matches</div>`;
  $("palette-list").querySelectorAll(".palette-item[data-id]").forEach((btn) => {
    btn.addEventListener("click", () => paletteItems($("palette-input").value).find((x) => x.id === btn.dataset.id)?.run());
  });
}

function openPalette() {
  $("palette-overlay").classList.add("open");
  $("palette-input").value = "";
  renderPalette("");
  $("palette-input").focus();
}

function closePalette() {
  $("palette-overlay").classList.remove("open");
}

function toggleShortcuts(force) {
  $("shortcuts-overlay").classList.toggle("open", force);
}

async function exportWorkspace() {
  const local = {
    format: "argoscout.workspace",
    version: 1,
    preferences: {
      theme: state.theme,
      locale: state.locale,
      privacy_layer: state.privacyLayer,
      country: state.country,
      llm_provider: state.llmProvider,
      llm_model: state.llmModel,
      reduced_motion: state.reducedMotion,
      copilot_dock_open: state.copilotDock,
    },
  };
  let bundle = local;
  if (state.apiKey) {
    try {
      const r = await fetch("/api/v1/workspace/export", { headers: authHeaders() });
      if (r.ok) bundle = await r.json();
    } catch {}
  }
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "argoscout-workspace.json";
  a.click();
}

async function importWorkspaceFile(file) {
  const text = await file.text();
  const bundle = JSON.parse(text);
  const prefs = bundle.preferences || bundle;
  if (state.apiKey) {
    await fetch("/api/v1/workspace/import", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(bundle),
    });
  }
  Object.assign(state, {
    theme: prefs.theme || state.theme,
    locale: prefs.locale || state.locale,
    privacyLayer: prefs.privacy_layer || state.privacyLayer,
    country: prefs.country || state.country,
    llmProvider: prefs.llm_provider || state.llmProvider,
    llmModel: prefs.llm_model || state.llmModel,
    reducedMotion: Boolean(prefs.reduced_motion),
    copilotDock: prefs.copilot_dock_open !== false,
  });
  fillSettingsForm();
  saveState();
  applyChrome();
}

function fillSettingsForm() {
  $("set-api-key").value = state.apiKey;
  $("set-admin-secret").value = state.adminSecret;
  $("set-llm-provider").value = state.llmProvider;
  $("set-theme").value = state.theme;
  $("set-locale").value = state.locale;
  $("set-privacy-layer").value = state.privacyLayer;
  $("set-country").value = state.country;
  $("set-reduced-motion").checked = state.reducedMotion;
  $("set-copilot-dock").checked = state.copilotDock;
}

function init() {
  fillSettingsForm();
  applyChrome();

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
  $("btn-probe-run").addEventListener("click", runProbe);
  $("btn-probe-pheromones").addEventListener("click", loadPheromones);
  $("btn-tiktok-analyze").addEventListener("click", runTikTokAnalyze);
  $("btn-inbox-poll").addEventListener("click", pollInbox);
  $("btn-inbox-refresh").addEventListener("click", loadInboxData);
  $("btn-sa-emit").addEventListener("click", emitStockArgosSignal);
  $("btn-sa-list").addEventListener("click", loadStockArgosSignals);
  $("btn-detective").addEventListener("click", runDetective);
  $("btn-osint").addEventListener("click", runOsint);
  $("btn-gdpr-scan").addEventListener("click", runGdprScan);
  document.querySelectorAll(".probe-mode").forEach((el) => {
    el.addEventListener("click", () => el.classList.toggle("active"));
  });
  $("set-llm-provider").addEventListener("change", () => { populateModels(); });

  document.querySelectorAll(".chip[data-agent]").forEach((el) => {
    el.addEventListener("click", () => { $("agent-goal").value = el.dataset.agent; });
  });
  document.querySelectorAll(".chip[data-msg]").forEach((el) => {
    el.addEventListener("click", () => { $("chat-input").value = el.dataset.msg; });
  });
  document.querySelectorAll(".chip[data-hero]").forEach((el) => {
    el.addEventListener("click", () => {
      $("hero-input").value = el.dataset.hero;
      runCopilot(el.dataset.hero, { fromHero: true });
    });
  });

  $("btn-hero-ask").addEventListener("click", () => runCopilot($("hero-input").value, { fromHero: true }));
  $("hero-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); runCopilot($("hero-input").value, { fromHero: true }); }
  });
  $("btn-copilot-send").addEventListener("click", () => {
    const msg = $("copilot-input").value.trim();
    $("copilot-input").value = "";
    runCopilot(msg);
  });
  $("copilot-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const msg = $("copilot-input").value.trim();
      $("copilot-input").value = "";
      runCopilot(msg);
    }
  });
  $("btn-copilot-toggle").addEventListener("click", () => {
    state.copilotDock = !document.body.classList.contains("copilot-open");
    applyChrome();
  });
  $("btn-copilot-close").addEventListener("click", () => {
    state.copilotDock = false;
    applyChrome();
  });
  $("btn-theme").addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : state.theme === "light" ? "system" : "dark";
    saveState();
    applyChrome();
    if ($("set-theme")) $("set-theme").value = state.theme;
  });
  $("btn-locale").addEventListener("click", () => {
    state.locale = resolvedLocale() === "en" ? "bg" : "en";
    saveState();
    applyChrome();
    if ($("set-locale")) $("set-locale").value = state.locale;
  });
  $("btn-palette").addEventListener("click", openPalette);
  $("btn-shortcuts").addEventListener("click", () => toggleShortcuts(true));
  $("palette-input").addEventListener("input", (e) => renderPalette(e.target.value));
  $("palette-overlay").addEventListener("click", (e) => { if (e.target.id === "palette-overlay") closePalette(); });
  $("shortcuts-overlay").addEventListener("click", (e) => { if (e.target.id === "shortcuts-overlay") toggleShortcuts(false); });
  $("btn-export-workspace").addEventListener("click", exportWorkspace);
  $("import-workspace").addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (file) importWorkspaceFile(file);
  });

  document.addEventListener("keydown", (e) => {
    const meta = e.ctrlKey || e.metaKey;
    if (meta && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); }
    if (meta && e.key.toLowerCase() === "j") {
      e.preventDefault();
      state.copilotDock = !document.body.classList.contains("copilot-open");
      applyChrome();
    }
    if (e.key === "Escape") {
      closePalette();
      toggleShortcuts(false);
    }
    if (e.key === "?" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) {
      toggleShortcuts(true);
    }
    if ($("palette-overlay").classList.contains("open") && e.key === "Enter") {
      e.preventDefault();
      $("palette-list").querySelector(".palette-item.active")?.click();
    }
  });

  populateModels();
  loadHealth();
  loadDashboard();
  showPage("dashboard");
}

window.revokeKey = revokeKey;
document.addEventListener("DOMContentLoaded", init);
