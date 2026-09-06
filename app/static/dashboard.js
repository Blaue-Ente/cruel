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
  { id: "apex", label: "Apex Master" },
  { id: "research", label: "Research" },
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
  researchId: localStorage.getItem("argos_research_id") || "",
  researchTab: localStorage.getItem("argos_research_tab") || "inbox",
  graphFocus: "",
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
  localStorage.setItem("argos_research_id", state.researchId || "");
  localStorage.setItem("argos_research_tab", state.researchTab || "inbox");
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
  if (id === "apex") loadLastApex();
  if (id === "research") {
    loadResearchForecast();
    loadEfficiencyTelemetry();
    if (state.researchId) {
      loadResearchInbox(state.researchId);
      loadMissionChips();
    }
    researchTab(state.researchTab || "inbox");
  }
  if (id === "settings") loadRiskStatus();
  loadCopilotContext();
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
      ${insecure ? `<div class="status-pill" style="margin-top:.35rem"><span class="dot warn"></span> Insecure admin secret</div>` : `<div class="status-pill" style="margin-top:.35rem"><span class="dot ok"></span> Admin ${d.security?.admin_secret_source || "ok"}</div>`}`;
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
  if (action === "open_apex") return showPage("apex");
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
    const byok = ["openrouter_configured", "openai_configured", "anthropic_configured", "groq_configured", "nvidia_configured", "hf_configured"]
      .filter((k) => d.llm?.[k]).length;
    $("stat-llm-sub").textContent = byok ? `${byok} BYOK provider(s)` : "Rule fallback";
    $("stat-scraperio").textContent = d.scraperio?.strategies?.length || 0;
    $("stat-scraperio-sub").textContent = d.scraperio?.engine || "Scraper.io";
    renderStrategies(d.scraperio);
    renderLlmHub(d.llm);
  } catch (e) {
    console.error(e);
  }
  try {
    const h = await fetch("/health");
    const health = await h.json();
    renderSecurityRing(health);
    const hint = $("admin-secret-hint");
    if (hint && health.security?.admin_secret_source === "generated_file") hint.classList.remove("hidden");
  } catch {}
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

function renderStrategies(scraperio) {
  const box = $("dash-strategies");
  const tbody = $("dash-strategy-table")?.querySelector("tbody");
  const strategies = scraperio?.strategies || scraperio?.available_strategies || [];
  const names = Array.isArray(strategies)
    ? strategies.map((s) => (typeof s === "string" ? s : s.name || s.id || JSON.stringify(s)))
    : Object.keys(strategies);
  if (box) {
    box.innerHTML = names.length
      ? names.map((n) => `<span class="strategy-chip">${n}</span>`).join("")
      : '<span class="muted-sm">No strategies advertised</span>';
  }
  if (tbody) {
    tbody.innerHTML = names.map((n) => `<tr><td>${n}</td><td>Fallback ladder</td></tr>`).join("");
  }
}

function renderLlmHub(llm) {
  const pills = $("dash-providers");
  const routing = $("dash-routing");
  const providers = [
    ["openrouter", llm?.openrouter_configured],
    ["openai", llm?.openai_configured],
    ["anthropic", llm?.anthropic_configured],
    ["groq", llm?.groq_configured],
    ["nvidia", llm?.nvidia_configured],
    ["hf", llm?.hf_configured],
    ["ollama", true],
  ];
  if (pills) {
    pills.innerHTML = providers.map(([name, on]) =>
      `<span class="intel-pill ${on ? "on" : ""}">${name}</span>`
    ).join("");
  }
  if (routing) {
    const light = (llm?.routing?.light || []).join(" → ") || "rule";
    const reason = (llm?.routing?.reasoning || []).join(" → ") || "rule";
    routing.textContent = `Light: ${light} · Reasoning: ${reason}`;
  }
  const ring = $("ring-llm");
  if (ring) ring.dataset.state = llm?.provider && llm.provider !== "rule_based" ? "ok" : "warn";
  const byokRing = $("ring-byok");
  if (byokRing) {
    const n = providers.filter(([, on]) => on).length;
    byokRing.dataset.state = n >= 2 ? "ok" : n === 1 ? "warn" : "bad";
  }
}

function renderSecurityRing(health) {
  const ring = $("ring-sec");
  if (!ring) return;
  ring.dataset.state = health.security?.admin_secret_insecure ? "bad" : "ok";
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
    const map = {
      openrouter: d.openrouter_models,
      openai: d.openai_models,
      anthropic: d.anthropic_models,
      groq: d.groq_models,
      nvidia: d.nvidia_models,
      huggingface: d.hf_models,
      ollama: d.ollama_models,
      auto: [...(d.openrouter_models || []), ...(d.groq_models || [])],
    };
    const models = map[state.llmProvider] || d.groq_models;
    (models || []).forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.name + (m.free ? " (free)" : "") + (m.tier ? ` · ${m.tier}` : "") + (m.speed ? ` · ${m.speed}` : "");
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

async function loadCopilotContext() {
  const box = $("copilot-context");
  if (!box) return;
  if (!state.apiKey) {
    box.textContent = "Save an API key to load scan context, pheromones, and obstacles.";
    return;
  }
  try {
    const r = await fetch("/api/v1/copilot/context", { headers: authHeaders() });
    if (!r.ok) {
      box.textContent = "Context unavailable.";
      return;
    }
    const d = await r.json();
    const last = d.last_scan ? `${d.last_scan.mode} ${d.last_scan.success ? "✓" : "✗"}` : "none";
    const pher = (d.pheromones || []).length;
    const obs = (d.obstacles || []).length;
    const risk = d.risk || {};
    const riskLabel = risk.any_enabled ? "high-risk on" : risk.acknowledged ? "risk ack, switches off" : "high-risk off";
    box.innerHTML = `Layer <strong>${d.privacy_layer || "—"}</strong> · last ${last} · pheromones ${pher} · obstacles ${obs} · ${riskLabel} · admin ${d.admin_secret_source}`;
  } catch {
    box.textContent = "Context offline.";
  }
}

function renderDossier(d) {
  const box = $("apex-dossier");
  if (!box) return;
  const findings = (d.key_findings || []).map((f) =>
    `<tr><td>${f.claim || ""}</td><td>${f.confidence ?? ""}</td><td>${(f.citation_ids || []).join(", ")}</td></tr>`
  ).join("");
  const cites = (d.citations || []).map((c) =>
    `<tr><td>${c.id}</td><td>${c.source}</td><td>${c.ok ? "✓" : "—"}</td><td>${(c.url || "").slice(0, 72)}</td></tr>`
  ).join("");
  const edges = ((d.graph || {}).edges || []).slice(0, 12).map((e) =>
    `<tr><td>${e.rel}</td><td>${(e.src || "").slice(0, 8)}</td><td>${(e.dst || "").slice(0, 8)}</td><td>${e.confidence ?? ""}</td></tr>`
  ).join("");
  box.innerHTML = `
    <div class="dossier-kicker">confidence ${d.confidence ?? "—"} · ${d.success ? "evidence found" : "gaps remain"} · probe ${d.live_probe_ran ? "ran" : "not used"}</div>
    <div class="dossier-headline">${d.headline || d.target || "Dossier"}</div>
    <p class="muted-sm">${d.executive_summary || ""}</p>
    <h4 style="margin:1rem 0 .4rem">Findings</h4>
    <table class="intel-table"><thead><tr><th>Claim</th><th>Conf.</th><th>Cite</th></tr></thead><tbody>${findings || "<tr><td colspan=3>None yet</td></tr>"}</tbody></table>
    <h4 style="margin:1rem 0 .4rem">Citations</h4>
    <table class="intel-table"><thead><tr><th>#</th><th>Source</th><th>OK</th><th>URL</th></tr></thead><tbody>${cites || "<tr><td colspan=4>—</td></tr>"}</tbody></table>
    <h4 style="margin:1rem 0 .4rem">Graph edges</h4>
    <table class="intel-table"><thead><tr><th>Rel</th><th>From</th><th>To</th><th>Conf.</th></tr></thead><tbody>${edges || "<tr><td colspan=4>No edges yet</td></tr>"}</tbody></table>
    <p class="muted-sm" style="margin-top:.8rem">${(d.gaps || []).join(" · ")}</p>
  `;
}

async function runApex() {
  if (!state.apiKey) return alert(t("need_key"));
  const target = $("apex-target").value.trim();
  if (!target) return;
  $("apex-dossier").innerHTML = '<div class="msg msg-sys">Apex planner running public-source steps…</div>';
  try {
    const r = await fetch("/api/v1/apex/run", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        target,
        include_people: $("apex-people").checked,
        include_corporate: $("apex-corporate").checked,
        include_archives: $("apex-archives").checked,
        llm_provider: state.llmProvider !== "auto" ? state.llmProvider : null,
        privacy_layer: state.privacyLayer || null,
        country: state.country || null,
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Apex failed");
    renderDossier(d);
    loadCopilotContext();
  } catch (e) {
    $("apex-dossier").innerHTML = `<div class="msg msg-sys">Error: ${e.message}</div>`;
  }
}

async function loadLastApex() {
  if (!state.apiKey) return;
  try {
    const r = await fetch("/api/v1/apex/last", { headers: authHeaders() });
    if (!r.ok) return;
    renderDossier(await r.json());
  } catch {}
}

function setArgosState(kind, caption, sub) {
  const stage = $("argos-stage");
  if (stage) stage.dataset.state = kind || "idle";
  if ($("argos-caption")) $("argos-caption").textContent = caption || "";
  if ($("argos-sub")) $("argos-sub").textContent = sub || "";
}

function researchTab(id) {
  if (!id) return;
  state.researchTab = id;
  localStorage.setItem("argos_research_tab", id);
  document.querySelectorAll(".research-tab").forEach((el) => el.classList.toggle("active", el.dataset.rtab === id));
  document.querySelectorAll(".research-panel").forEach((el) => el.classList.toggle("active", el.id === `rtab-${id}`));
  if (id === "graph" && state.researchId) loadResearchGraph();
  if (id === "inspector") loadEfficiencyTelemetry();
  if (id === "report" && state.researchId) loadSnapshotSelects();
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function loadResearchForecast() {
  const box = $("research-forecast");
  if (!box || !state.apiKey) return;
  const mode = $("research-mode")?.value || "quick";
  const verify = $("research-workflow")?.value === "discover_then_verify";
  try {
    const r = await fetch(`/api/v1/research/estimate?mode=${mode}&verify=${verify}`, { headers: authHeaders() });
    if (!r.ok) return;
    const d = await r.json();
    const disc = d.discovery || {};
    const ver = d.verification;
    box.textContent = `Forecast (not a bill): ~${disc.requests || "?"} requests, ${disc.seconds || "?"}s discovery`
      + (ver ? `; verify ~${ver.requests} extra requests / ${ver.seconds}s` : "")
      + ". " + (d.note || "");
  } catch {}
}

function renderInbox(pack) {
  const box = $("research-inbox");
  if (!box) return;
  const docs = pack.documents || [];
  if (!docs.length) {
    box.innerHTML = '<div class="empty-state">No materials yet. Run Discovery.</div>';
    return;
  }
  box.innerHTML = docs.map((d) => `
    <article class="research-item" data-id="${d.id}">
      <header>
        <strong>${d.title || d.url || "Untitled trace"}</strong>
        <span class="badge-unverified">${d.verification_status || "not_requested"}</span>
      </header>
      <p class="muted-sm">${d.publisher || ""} · ${d.method || ""} · ${d.is_snippet ? "search snippet (trace)" : d.source_type}</p>
      <p class="muted-sm">${(d.excerpt || "").slice(0, 220)}</p>
      <p class="muted-sm">${d.url || ""}</p>
      <label class="toggle-row"><input type="checkbox" class="research-pick" value="${d.id}" /><span>Select</span></label>
    </article>`).join("");
}

function renderVerify(pack) {
  const box = $("research-verify-out");
  if (!box) return;
  const claims = pack.claims || pack.results || [];
  if (!claims.length) {
    box.innerHTML = '<div class="empty-state">Nothing verified yet.</div>';
    return;
  }
  const rows = pack.results
    ? pack.results.map((row) => {
        const c = row.claim || {};
        const a = row.assessment || {};
        return { ...c, explanation: a.explanation, dimensions: a.dimensions };
      })
    : claims;
  box.innerHTML = rows.map((c) => `
    <article class="research-item">
      <header>
        <strong>${(c.text || "").slice(0, 180)}</strong>
        <span class="badge-status ${c.status || ""}">${c.status || "not_requested"}</span>
      </header>
      <p class="muted-sm">${c.explanation || "Not assessed. A missing confirmation is not a false claim."}</p>
      <button class="btn btn-secondary btn-sm research-evidence-btn" data-claim="${c.id}" type="button">Show evidence</button>
    </article>`).join("");
  box.querySelectorAll(".research-evidence-btn").forEach((btn) => {
    btn.addEventListener("click", () => showClaimEvidence(pack, btn.dataset.claim));
  });
}

function showClaimEvidence(pack, claimId) {
  researchTab("evidence");
  const box = $("research-evidence");
  const row = (pack.results || []).find((item) => (item.claim || {}).id === claimId);
  const evidence = row?.evidence || [];
  if (!evidence.length) {
    box.innerHTML = '<div class="empty-state">No evidence links for that claim yet.</div>';
    return;
  }
  box.innerHTML = evidence.map((e) => `
    <article class="research-item">
      <header><strong>${e.title || e.document_id}</strong><span class="badge-status">${e.stance}</span></header>
      <p class="muted-sm">${e.reliability?.note || ""}</p>
      <p class="muted-sm">${(e.excerpt || "").slice(0, 280)}</p>
    </article>`).join("");
}

function renderReport(pack) {
  const box = $("research-report");
  if (!box) return;
  const cov = pack.coverage_map || pack.task?.coverage || {};
  const gaps = pack.gap_map || [];
  const ents = pack.entities || [];
  box.innerHTML = `
    <article class="research-item"><strong>Coverage</strong>
      <p class="muted-sm">Ran: ${(cov.ran || []).join(", ") || "—"}</p>
      <p class="muted-sm">Blocked: ${(cov.blocked || []).join(", ") || "—"}</p>
      <p class="muted-sm">Out of scope: ${(cov.out_of_scope || []).join(", ") || "—"}</p>
    </article>
    <article class="research-item"><strong>Candidates (not merged by name)</strong>
      ${ents.map((e) => `<p class="muted-sm">${e.kind}: ${e.name} · ${e.link_status}${e.merged_into ? " → " + e.merged_into : ""}</p>`).join("") || "<p class='muted-sm'>None</p>"}
    </article>
    <article class="research-item"><strong>Evidence gaps</strong>
      ${gaps.map((g) => `<p class="muted-sm">${g.status}: ${g.text}<br>${g.next}</p>`).join("") || "<p class='muted-sm'>No gap list yet.</p>"}
    </article>`;
}

async function loadResearchInbox(taskId, extra) {
  if (!state.apiKey || !taskId) return;
  const q = $("research-filter")?.value || "";
  const t = $("research-type-filter")?.value || "";
  const r = await fetch(`/api/v1/research/${taskId}/inbox?q=${encodeURIComponent(q)}&source_type=${encodeURIComponent(t)}`, { headers: authHeaders() });
  if (!r.ok) return;
  const pack = await r.json();
  renderInbox(pack);
  renderVerify(extra || pack);
  renderReport(pack);
  applyMission(pack.mission);
  if ($("research-inspector")) $("research-inspector").textContent = JSON.stringify(pack, null, 2);
  const counts = pack.counts || {};
  $("research-run-status").textContent = `${pack.task?.status || ""} · ${counts.documents || 0} materials · ${counts.unverified || 0} unverified`;
  if (state.researchTab === "graph") loadResearchGraph();
  loadEfficiencyTelemetry();
  loadSnapshotSelects();
  return pack;
}

async function runResearch() {
  if (!state.apiKey) return alert(t("need_key"));
  const query = $("research-query")?.value.trim();
  if (!query) return;
  setArgosState("discover", "Argos is scanning public traces", "Search snippets stay traces until you choose to verify.");
  $("research-run-status").textContent = "Discovery running…";
  $("research-inbox").innerHTML = '<div class="loading-state">Collecting allowed sources…</div>';
  try {
    const r = await fetch("/api/v1/research/discover", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        query,
        mode: $("research-mode").value,
        workflow: $("research-workflow").value,
        include_people: $("research-people").checked,
        privacy_layer: state.privacyLayer || null,
        country: state.country || null,
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Discovery failed");
    state.researchId = d.task.id;
    saveState();
    const done = d.task.status;
    setArgosState(done === "error" ? "error" : "done", "Inbox ready — unverified", d.banner);
    renderInbox(d);
    renderVerify(d);
    renderReport(d);
    applyMission(d.mission);
    if ($("research-inspector")) $("research-inspector").textContent = JSON.stringify(d, null, 2);
    $("research-run-status").textContent = `${done} · ${d.counts?.documents || 0} materials`;
    loadEfficiencyTelemetry();
    loadSnapshotSelects();
    if (state.researchTab === "graph") loadResearchGraph();
    if (d.task.workflow === "discover_then_verify") {
      setArgosState("verify", "Weighing collected evidence", "No single truth score. Independence groups copies of the same story.");
      researchTab("verify");
    }
  } catch (e) {
    setArgosState("error", "Discovery stopped", e.message);
    $("research-inbox").innerHTML = `<div class="error-state">${e.message}</div>`;
  }
}

async function verifyResearch() {
  if (!state.apiKey) return alert(t("need_key"));
  if (!state.researchId) return alert("Run Discovery first.");
  const ids = [...document.querySelectorAll(".research-pick:checked")].map((el) => el.value);
  setArgosState("verify", "Verification in motion", "Original excerpts are not rewritten.");
  try {
    const r = await fetch(`/api/v1/research/${state.researchId}/verify`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        scope: $("research-v-scope").value,
        level: $("research-v-level").value,
        ids,
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Verify failed");
    setArgosState("done", "Assessments ready", d.banner);
    renderVerify(d);
    await loadResearchInbox(state.researchId, d);
    loadMissionChips();
    if (state.researchTab === "graph") loadResearchGraph();
    researchTab("verify");
  } catch (e) {
    setArgosState("error", "Verification stopped", e.message);
  }
}

async function replayResearch() {
  if (!state.researchId) return;
  const r = await fetch(`/api/v1/research/${state.researchId}/replay`, { method: "POST", headers: authHeaders() });
  const d = await r.json();
  renderVerify(d);
}

async function cancelResearch() {
  if (!state.researchId) return;
  await fetch(`/api/v1/research/${state.researchId}/cancel`, { method: "POST", headers: authHeaders() });
  setArgosState("idle", "Cancelled", "No new collection will start.");
}

async function exportResearch() {
  if (!state.researchId) return;
  const fmt = $("research-export-format")?.value || "json";
  const r = await fetch(`/api/v1/research/${state.researchId}/export?format=${encodeURIComponent(fmt)}`, { headers: authHeaders() });
  const d = await r.json();
  if (!r.ok) throw new Error(d.detail || "Export failed");
  let blob;
  let name;
  if (fmt === "markdown") {
    blob = new Blob([d.markdown || ""], { type: "text/markdown" });
    name = "argoscout-dossier.md";
  } else if (fmt === "html") {
    blob = new Blob([d.html || ""], { type: "text/html" });
    name = "argoscout-dossier.html";
  } else {
    blob = new Blob([JSON.stringify(d, null, 2)], { type: "application/json" });
    name = "argoscout-research.json";
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}

function addCopilotCard(card) {
  const el = document.createElement("article");
  el.className = "copilot-card";
  el.innerHTML = `<strong>${esc(card.title || "Mission")}</strong>
    <p class="muted-sm">${esc(card.note || "")}</p>
    ${card.ran ? `<p class="muted-sm">Ran: ${esc((card.ran || []).join(", "))}</p>` : ""}`;
  $("copilot-messages")?.appendChild(el);
  $("copilot-messages").scrollTop = $("copilot-messages").scrollHeight;
}

function applyMission(mission) {
  const chips = mission?.chips || [];
  renderMissionChips(chips);
  if (chips.length) {
    state.copilotDock = true;
    applyChrome();
  }
}

function renderMissionChips(chips) {
  const box = $("copilot-action-chips");
  if (!box) return;
  if (!chips.length) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  box.innerHTML = chips.map((c) =>
    `<button type="button" class="mission-chip" data-chip="${esc(c.id)}" title="${esc(c.intent)}">${esc(c.label)}</button>`
  ).join("");
  box.querySelectorAll(".mission-chip").forEach((btn) => {
    btn.addEventListener("click", () => previewChip(btn.dataset.chip));
  });
}

async function loadMissionChips() {
  if (!state.apiKey || !state.researchId) return;
  try {
    const r = await fetch(`/api/v1/research/${state.researchId}/chips`, { headers: authHeaders() });
    if (!r.ok) return;
    applyMission(await r.json());
  } catch {}
}

async function previewChip(chipId) {
  if (!state.researchId || !chipId) return;
  const r = await fetch(`/api/v1/research/${state.researchId}/chips/${chipId}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ confirmed: false }),
  });
  const d = await r.json();
  const box = $("chip-confirm");
  if (!box) return;
  const fc = d.forecast || d.chip?.cost_forecast || {};
  box.hidden = false;
  box.innerHTML = `<div>${esc(d.message || "Confirm this action.")}</div>
    <div class="muted-sm">Forecast: ~${esc(fc.requests ?? 0)} requests, ${esc(fc.byok_cost_est || "$0.00")} · ${esc(fc.note || "Not a bill.")}</div>
    <div class="row">
      <button class="btn btn-primary btn-sm" type="button" id="chip-go">Confirm & run</button>
      <button class="btn btn-secondary btn-sm" type="button" id="chip-cancel">Cancel</button>
    </div>`;
  $("chip-go")?.addEventListener("click", () => runChip(chipId));
  $("chip-cancel")?.addEventListener("click", () => { box.hidden = true; box.innerHTML = ""; });
}

async function runChip(chipId) {
  const box = $("chip-confirm");
  if (box) { box.hidden = true; box.innerHTML = ""; }
  addCopilotMsg("Running confirmed chip…", "sys");
  try {
    const r = await fetch(`/api/v1/research/${state.researchId}/chips/${chipId}`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ confirmed: true }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || d.error || "Chip failed");
    addCopilotCard(d.card || { title: d.chip?.label, note: d.banner, ran: d.summary?.ran });
    if (d.inbox) {
      renderInbox(d.inbox);
      renderVerify(d.inbox);
      renderReport(d.inbox);
    }
    applyMission((d.inbox || {}).mission);
    loadResearchGraph();
    loadEfficiencyTelemetry();
    loadSnapshotSelects();
  } catch (e) {
    addCopilotMsg("Chip error: " + e.message, "sys");
  }
}

function layoutGraph(nodes) {
  const cx = 460, cy = 270;
  const rings = { target: 0, organization: 120, person: 190, host: 190, identifier: 250, artifact: 310 };
  const grouped = {};
  nodes.forEach((n) => {
    const k = n.kind || "artifact";
    (grouped[k] = grouped[k] || []).push(n);
  });
  const placed = [];
  Object.entries(grouped).forEach(([kind, list]) => {
    const r = rings[kind] ?? 280;
    list.forEach((n, i) => {
      const offset = kind === "host" ? 0.4 : kind === "person" ? -0.3 : 0;
      const angle = (Math.PI * 2 * i) / Math.max(list.length, 1) - Math.PI / 2 + offset;
      placed.push({
        ...n,
        x: r === 0 ? cx : cx + Math.cos(angle) * r,
        y: r === 0 ? cy : cy + Math.sin(angle) * r * 0.78,
      });
    });
  });
  return placed;
}

const NODE_MARK = {
  target: "◎",
  organization: "▣",
  person: "◉",
  host: "⬡",
  identifier: "#",
  artifact: "▦",
};

function renderGraph(pack) {
  const svg = $("research-graph");
  if (!svg) return;
  const nodes = layoutGraph(pack.nodes || []);
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const edges = pack.edges || [];
  const lines = edges.map((e) => {
    const a = byId[e.source || e.source_id];
    const b = byId[e.target || e.target_id];
    if (!a || !b) return "";
    const dash = e.dash && e.dash !== "none" ? `stroke-dasharray="${esc(e.dash)}"` : "";
    const selected = state.graphFocus === e.id ? "stroke-width=\"3\"" : "stroke-width=\"1.6\"";
    return `<line class="graph-edge" data-id="${esc(e.id)}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"
      stroke="${esc(e.stroke || "#f59e0b")}" ${dash} opacity="${e.opacity ?? 0.7}" ${selected}>
      <title>${esc(e.tooltip || e.rel_type)}</title></line>`;
  }).join("");
  const dots = nodes.map((n) => {
    const fill = n.kind === "target" ? "#76b900" : n.kind === "person" ? "#5b8cff" : n.kind === "host" ? "#94a3b8" : "#1e2433";
    const ring = state.graphFocus === n.id ? "#eef1f7" : "#2a3144";
    return `<g class="graph-node" data-id="${esc(n.id)}" transform="translate(${n.x},${n.y})">
      <circle r="18" fill="${fill}" stroke="${ring}" stroke-width="2"/>
      <text text-anchor="middle" dy="-22" class="badge">${esc(n.type || n.kind)}</text>
      <text text-anchor="middle" dy="5">${esc(NODE_MARK[n.kind] || "•")}</text>
      <text text-anchor="middle" dy="34">${esc((n.label || "").slice(0, 22))}</text>
    </g>`;
  }).join("");
  svg.innerHTML = `<rect width="920" height="540" fill="transparent"/>${lines}${dots}`;
  svg.querySelectorAll(".graph-edge").forEach((el) => {
    el.addEventListener("click", (ev) => { ev.stopPropagation(); openGraphDrawer(el.dataset.id); });
  });
  svg.querySelectorAll(".graph-node").forEach((el) => {
    el.addEventListener("click", (ev) => { ev.stopPropagation(); openGraphDrawer(el.dataset.id); });
  });
}

async function loadResearchGraph() {
  if (!state.apiKey || !state.researchId) return;
  const svg = $("research-graph");
  if (svg) svg.innerHTML = `<text x="20" y="30" fill="#8b93a7">Loading graph…</text>`;
  try {
    const r = await fetch(`/api/v1/research/${state.researchId}/graph`, { headers: authHeaders() });
    if (!r.ok) return;
    renderGraph(await r.json());
  } catch (e) {
    if (svg) svg.innerHTML = `<text x="20" y="30" fill="#ff6b6b">${esc(e.message)}</text>`;
  }
}

async function openGraphDrawer(elementId) {
  state.graphFocus = elementId;
  const drawer = $("graph-drawer");
  const body = $("graph-drawer-body");
  if (!drawer || !body) return;
  drawer.hidden = false;
  body.innerHTML = "<p class='muted-sm'>Loading evidence…</p>";
  try {
    const r = await fetch(`/api/v1/research/${state.researchId}/graph/${encodeURIComponent(elementId)}`, { headers: authHeaders() });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Not found");
    const el = d.element || {};
    $("graph-drawer-title").textContent = el.label || el.rel_type || "Inspector";
    const sources = (d.sources || []).map((s) => `
      <div class="src">
        <div>${esc(s.title || "")}</div>
        <div>${esc(s.url || "")}</div>
        <div>${esc(s.fetched_at || "")} · ${esc(s.method || "")}</div>
        <p>${esc((s.excerpt || "").slice(0, 280))}</p>
        <div>sha256 ${esc((s.content_hash || "").slice(0, 16))}…</div>
      </div>`).join("") || "<p class='muted-sm'>No source snippets on this element.</p>";
    const fc = d.verify?.forecast || {};
    const canVerify = d.verify?.available;
    body.innerHTML = `
      <p class="muted-sm">${esc(d.kind)} · ${esc(el.layer || el.kind || "")} · ${esc(el.rel_type || "")}</p>
      <p class="muted-sm">${esc((d.confidence && JSON.stringify(d.confidence)) || d.snippet || "")}</p>
      ${sources}
      ${canVerify ? `<button class="btn btn-primary" type="button" id="btn-verify-edge">Verify Only This Edge</button>
        <p class="muted-sm">Forecast: ~${esc(fc.requests ?? 0)} requests, ${esc(fc.byok_cost_est || "$0.00")}</p>` : ""}`;
    $("btn-verify-edge")?.addEventListener("click", () => verifyGraphEdge(elementId, fc));
    loadResearchGraph();
  } catch (e) {
    body.innerHTML = `<p class="error-state">${esc(e.message)}</p>`;
  }
}

async function verifyGraphEdge(elementId, forecast) {
  const fc = forecast || {};
  if (!window.confirm(`Verify only this edge?\nForecast: ~${fc.requests ?? 0} requests, ${fc.byok_cost_est || "$0.00"}`)) return;
  try {
    const r = await fetch(`/api/v1/research/${state.researchId}/graph/${encodeURIComponent(elementId)}/verify`, {
      method: "POST",
      headers: authHeaders(),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Verify failed");
    if (d.graph) renderGraph(d.graph);
    await loadResearchInbox(state.researchId, d.verification);
    openGraphDrawer(elementId);
    addCopilotCard({ title: "Edge verified", note: d.verification?.banner, ran: ["verify_analyze"] });
  } catch (e) {
    alert(e.message);
  }
}

function closeGraphDrawer() {
  const drawer = $("graph-drawer");
  if (drawer) drawer.hidden = true;
  state.graphFocus = "";
}

function renderTelemetry(t) {
  if (!t) return "";
  return `
    <article class="telemetry-card"><div class="kicker">Pheromones active</div><div class="value">${t.pheromones_active ?? 0}</div><p class="muted-sm">${t.mapped_routes ?? 0} mapped routes</p></article>
    <article class="telemetry-card"><div class="kicker">Requests saved</div><div class="value">${t.requests_avoided ?? 0}</div><p class="muted-sm">${t.bandwidth_savings?.http_calls_skipped ?? 0} HTTP skips</p></article>
    <article class="telemetry-card"><div class="kicker">Cost efficiency</div><div class="value">${t.cost_efficiency_index ?? 0}</div><p class="muted-sm">${esc(t.bandwidth_savings?.byok_cost_est || "$0.00")} est. · not a bill</p></article>`;
}

async function loadEfficiencyTelemetry() {
  if (!state.apiKey) return;
  try {
    const r = await fetch("/api/v1/research/memory/pheromones", { headers: authHeaders() });
    if (!r.ok) return;
    const t = await r.json();
    const grid = $("efficiency-telemetry");
    if (grid) grid.innerHTML = renderTelemetry(t);
    const live = $("live-telemetry");
    if (live) {
      live.hidden = false;
      live.innerHTML = `<span>Pheromones ${t.pheromones_active ?? 0}</span><span>Saved ${t.requests_avoided ?? 0} req</span><span>CEI ${t.cost_efficiency_index ?? 0}</span>`;
    }
  } catch {}
}

async function inspectPheromoneMap() {
  if (!state.apiKey) return alert(t("need_key"));
  researchTab("inspector");
  const r = await fetch("/api/v1/research/memory/pheromones/map", { headers: authHeaders() });
  const d = await r.json();
  if ($("pheromone-map-view")) $("pheromone-map-view").textContent = JSON.stringify(d, null, 2);
}

async function flushPheromoneCache() {
  if (!state.apiKey) return alert(t("need_key"));
  if (!window.confirm("Flush cached pheromone routes? Historical savings counters stay. Fresh probing will spend requests again.")) return;
  const r = await fetch("/api/v1/research/memory/pheromones/flush", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ confirm: true }),
  });
  const d = await r.json();
  if ($("pheromone-map-view")) $("pheromone-map-view").textContent = JSON.stringify(d, null, 2);
  loadEfficiencyTelemetry();
}

async function loadSnapshotSelects() {
  if (!state.apiKey || !state.researchId) return;
  try {
    const r = await fetch(`/api/v1/research/${state.researchId}/snapshots`, { headers: authHeaders() });
    if (!r.ok) return;
    const d = await r.json();
    const snaps = d.snapshots || [];
    const opts = snaps.map((s) => `<option value="${esc(s.id)}">${esc(s.trigger)} · ${esc((s.timestamp || "").slice(0, 19))}</option>`).join("");
    if ($("snap-left")) $("snap-left").innerHTML = opts;
    if ($("snap-right")) $("snap-right").innerHTML = opts;
    if (snaps.length >= 2 && $("snap-right")) $("snap-right").selectedIndex = 0;
    if (snaps.length >= 2 && $("snap-left")) $("snap-left").selectedIndex = Math.min(1, snaps.length - 1);
  } catch {}
}

function renderDiffPack(d) {
  const box = $("research-diff");
  if (!box) return;
  const added = d.added || {};
  const removed = d.removed || {};
  const modified = d.modified || {};
  const list = (arr, cls, label) => {
    const items = arr || [];
    if (!items.length) return "";
    return `<article class="research-item"><strong class="${cls}">${label}</strong>${
      items.map((item) => `<p class="muted-sm">${esc(item.name || item.text || item.title || item.note || item.url || JSON.stringify(item))}</p>`).join("")
    }</article>`;
  };
  box.innerHTML = [
    list([...(added.personnel || []).map((n) => ({ name: n })), ...(added.entities || [])], "diff-added", "Added"),
    list(added.domains || [], "diff-added", "Added domains"),
    list(added.claims || added.documents || [], "diff-added", "Added claims / materials"),
    list([...(removed.personnel || []).map((n) => ({ name: n })), ...(removed.entities || [])], "diff-removed", "Removed"),
    list(removed.domains || [], "diff-removed", "Removed domains"),
    list(modified.claims || modified.documents || [], "diff-modified", "Modified"),
    d.note ? `<p class="muted-sm">${esc(d.note)}</p>` : "",
  ].join("") || "<div class='empty-state'>No delta between these snapshots.</div>";
}

async function compareSnapshots() {
  const left = $("snap-left")?.value;
  const right = $("snap-right")?.value;
  if (!left || !right) return alert("Need two snapshots.");
  const r = await fetch(`/api/v1/research/snapshots/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`, { headers: authHeaders() });
  const d = await r.json();
  if (!r.ok) return alert(d.detail || "Compare failed");
  renderDiffPack(d);
}

async function runLookback() {
  if (!state.researchId) return;
  const r = await fetch(`/api/v1/research/${state.researchId}/lookback`, { headers: authHeaders() });
  const d = await r.json();
  if (!r.ok) return alert(d.detail || "Lookback failed");
  renderDiffPack(d);
  loadSnapshotSelects();
}

async function openPlaybook() {
  $("playbook-overlay").classList.add("open");
  try {
    const r = await fetch("/api/v1/playbook");
    const d = await r.json();
    $("playbook-stance").textContent = d.stance || "";
    $("playbook-list").innerHTML = (d.entries || []).map((e) => `
      <article class="playbook-item" data-id="${e.id}">
        <div class="tag">${e.category}</div>
        <h4>${e.name}</h4>
        <p class="muted-sm">${e.summary}</p>
        <p class="muted-sm"><strong>Use when:</strong> ${e.use_when}</p>
        <p class="muted-sm"><strong>Expected:</strong> ${e.expected}</p>
        <p class="muted-sm"><strong>Legal:</strong> ${e.legal}</p>
      </article>`).join("");
  } catch (e) {
    $("playbook-list").textContent = "Could not load playbook.";
  }
}

function closePlaybook() {
  $("playbook-overlay")?.classList.remove("open");
}

const RISK_CAP_IDS = {
  flaresolverr: "risk-flaresolverr",
  tls_impersonate: "risk-tls",
  fingerprint_profiles: "risk-fingerprint",
  linkedin_public_fetch: "risk-linkedin",
  github_commit_emails: "risk-github",
};

function closeRiskNotice() {
  $("risk-overlay")?.classList.remove("open");
}

function applyRiskStatus(d) {
  const line = $("risk-status-line");
  const toggles = $("risk-toggles");
  if (!line || !d) return;
  const caps = d.capabilities || {};
  const enabled = Object.entries(caps).filter(([, on]) => on).map(([name]) => name);
  if (!d.acknowledged) {
    line.textContent = "All high-risk options are off until you read and accept the notice.";
    toggles?.classList.add("hidden");
    return;
  }
  line.textContent = enabled.length
    ? `Notice accepted. Enabled: ${enabled.join(", ")}`
    : "Notice accepted. Switches stay off until you enable them below.";
  toggles?.classList.remove("hidden");
  Object.entries(RISK_CAP_IDS).forEach(([cap, id]) => {
    const el = $(id);
    if (el) el.checked = Boolean(caps[cap]);
  });
}

async function loadRiskStatus() {
  if (!state.apiKey || !$("risk-status-line")) return;
  try {
    const r = await fetch("/api/v1/compliance/risk/status", { headers: authHeaders() });
    if (!r.ok) return;
    applyRiskStatus(await r.json());
  } catch {}
}

async function openRiskNotice() {
  $("risk-overlay")?.classList.add("open");
  $("risk-phrase") && ($("risk-phrase").value = "");
  $("risk-authorized") && ($("risk-authorized").checked = false);
  try {
    const r = await fetch("/api/v1/compliance/risk");
    const d = await r.json();
    const text = resolvedLocale() === "bg" ? d.notice_bg : d.notice_en;
    if ($("risk-notice-text")) $("risk-notice-text").textContent = text || "";
  } catch (e) {
    if ($("risk-notice-text")) $("risk-notice-text").textContent = "Could not load the operator notice.";
  }
}

async function acceptRiskNotice() {
  if (!state.apiKey) {
    alert(t("need_key"));
    showPage("settings");
    return;
  }
  if (!$("risk-authorized")?.checked) {
    alert("Confirm lawful basis / authorized use before accepting.");
    return;
  }
  const phrase = ($("risk-phrase")?.value || "").trim();
  try {
    const r = await fetch("/api/v1/compliance/risk/acknowledge", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ phrase, authorized_use: true, capabilities: {} }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || d.error || "Acknowledgment rejected");
    applyRiskStatus(d);
    closeRiskNotice();
  } catch (e) {
    alert(e.message);
  }
}

async function saveRiskCaps() {
  if (!state.apiKey) return alert(t("need_key"));
  const capabilities = {};
  Object.entries(RISK_CAP_IDS).forEach(([cap, id]) => {
    capabilities[cap] = Boolean($(id)?.checked);
  });
  try {
    const r = await fetch("/api/v1/compliance/risk/capabilities", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ capabilities }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || d.error || "Could not save switches");
    applyRiskStatus(d);
  } catch (e) {
    alert(e.message);
  }
}

async function revokeRisk() {
  if (!state.apiKey) return alert(t("need_key"));
  if (!window.confirm("Revoke the acknowledgment and turn every high-risk switch off?")) return;
  try {
    const r = await fetch("/api/v1/compliance/risk/revoke", { method: "POST", headers: authHeaders() });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Revoke failed");
    applyRiskStatus(d);
    Object.values(RISK_CAP_IDS).forEach((id) => { if ($(id)) $(id).checked = false; });
  } catch (e) {
    alert(e.message);
  }
}

async function postRiskOp(path, body) {
  if (!state.apiKey) return alert(t("need_key"));
  const out = $("risk-ops-result");
  if (out) out.textContent = "Running…";
  try {
    const r = await fetch(path, { method: "POST", headers: authHeaders(), body: JSON.stringify(body) });
    const d = await r.json();
    if (out) out.textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    if (out) out.textContent = "Error: " + e.message;
  }
}

function runFlareSolverrFetch() {
  const url = $("risk-fs-url")?.value.trim();
  if (!url) return alert("Enter a target URL.");
  return postRiskOp("/api/v1/recon/flaresolverr", { url });
}

function runLinkedInFetch() {
  const url = $("risk-li-url")?.value.trim();
  if (!url) return alert("Enter a LinkedIn URL.");
  return postRiskOp("/api/v1/osint/linkedin", { url });
}

function runGithubEmailsFetch() {
  const owner = $("risk-gh-owner")?.value.trim();
  const repo = $("risk-gh-repo")?.value.trim();
  const url = $("risk-gh-url")?.value.trim();
  if (!url && (!owner || !repo)) return alert("Enter owner and repo, or a github.com URL.");
  return postRiskOp("/api/v1/osint/github-emails", { owner, repo, url, limit: 20 });
}

function paletteItems(query) {
  const q = query.toLowerCase();
  const actions = [
    { id: "act-copilot", label: "Ask Copilot", run: () => { closePalette(); $("copilot-input").focus(); state.copilotDock = true; applyChrome(); } },
    { id: "act-health", label: "Inspect health", run: () => { closePalette(); runCopilot("Inspect system health"); } },
    { id: "act-apex", label: "Run Apex Master Mode", run: () => { closePalette(); showPage("apex"); $("apex-target")?.focus(); } },
    { id: "act-playbook", label: "Open Feature Inspector", run: () => { closePalette(); openPlaybook(); } },
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
  $("btn-apex-run")?.addEventListener("click", runApex);
  $("btn-research-run")?.addEventListener("click", runResearch);
  $("btn-research-cancel")?.addEventListener("click", cancelResearch);
  $("btn-research-export")?.addEventListener("click", exportResearch);
  $("btn-research-verify")?.addEventListener("click", verifyResearch);
  $("btn-research-replay")?.addEventListener("click", replayResearch);
  $("btn-research-diff")?.addEventListener("click", compareSnapshots);
  $("btn-research-lookback")?.addEventListener("click", runLookback);
  $("btn-pheromone-map")?.addEventListener("click", inspectPheromoneMap);
  $("btn-pheromone-flush")?.addEventListener("click", flushPheromoneCache);
  $("graph-drawer-close")?.addEventListener("click", closeGraphDrawer);
  $("research-mode")?.addEventListener("change", loadResearchForecast);
  $("research-workflow")?.addEventListener("change", loadResearchForecast);
  $("research-filter")?.addEventListener("input", () => state.researchId && loadResearchInbox(state.researchId));
  $("research-type-filter")?.addEventListener("change", () => state.researchId && loadResearchInbox(state.researchId));
  document.querySelectorAll(".research-tab").forEach((btn) => {
    btn.addEventListener("click", () => researchTab(btn.dataset.rtab));
  });
  document.querySelectorAll(".chip[data-research]").forEach((el) => {
    el.addEventListener("click", () => { $("research-query").value = el.dataset.research; });
  });
  $("btn-playbook")?.addEventListener("click", openPlaybook);
  $("btn-playbook-close")?.addEventListener("click", closePlaybook);
  $("btn-risk-notice")?.addEventListener("click", openRiskNotice);
  $("btn-risk-close")?.addEventListener("click", closeRiskNotice);
  $("btn-risk-accept")?.addEventListener("click", acceptRiskNotice);
  $("btn-risk-save-caps")?.addEventListener("click", saveRiskCaps);
  $("btn-risk-revoke")?.addEventListener("click", revokeRisk);
  $("btn-risk-fs")?.addEventListener("click", runFlareSolverrFetch);
  $("btn-risk-li")?.addEventListener("click", runLinkedInFetch);
  $("btn-risk-gh")?.addEventListener("click", runGithubEmailsFetch);
  $("risk-overlay")?.addEventListener("click", (e) => { if (e.target.id === "risk-overlay") closeRiskNotice(); });
  $("risk-phrase")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); acceptRiskNotice(); }
  });
  document.querySelectorAll(".chip[data-apex]").forEach((el) => {
    el.addEventListener("click", () => { $("apex-target").value = el.dataset.apex; });
  });
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
  $("playbook-overlay")?.addEventListener("click", (e) => { if (e.target.id === "playbook-overlay") closePlaybook(); });
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
    if (meta && e.key.toLowerCase() === "i") { e.preventDefault(); openPlaybook(); }
    if (e.key === "Escape") {
      closePalette();
      closePlaybook();
      closeRiskNotice();
      closeGraphDrawer();
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
  loadCopilotContext();
  loadRiskStatus();
  showPage("dashboard");
}

window.revokeKey = revokeKey;
document.addEventListener("DOMContentLoaded", init);
