let allCalls = [];
let currentTab = "calls";

function fmt(n, digits = 0) {
  if (n == null) return "—";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return Number(n).toFixed(digits);
}

function fmtCost(v) {
  if (!v) return "$0.0000";
  if (v < 0.0001) return "<$0.0001";
  return "$" + v.toFixed(4);
}

function fmtTime(ts) {
  if (!ts) return "—";
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function providerPill(provider) {
  return `<span class="provider-pill pill-${provider || "unknown"}">${provider || "?"}</span>`;
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

function showTab(tab) {
  currentTab = tab;
  document.getElementById("calls-tab").style.display = tab === "calls" ? "" : "none";
  document.getElementById("stats-tab").style.display = tab === "stats" ? "" : "none";
  document.getElementById("settings-panel").style.display = tab === "settings" ? "" : "none";
  document.getElementById("detail-panel").style.display = "none";

  ["calls", "stats", "settings"].forEach((t) => {
    document.getElementById(`tab-${t}`)?.classList.toggle("active", t === tab);
  });

  if (tab === "stats") renderStats();
  if (tab === "settings") loadSettings();
}

// ── Call List ─────────────────────────────────────────────────────────────────

function renderCalls(calls) {
  const list = document.getElementById("call-list");
  if (!calls.length) {
    list.innerHTML = `<div class="empty"><div class="empty-icon">📡</div>No LLM calls detected yet.<br>Make an API call on this page.</div>`;
    return;
  }

  list.innerHTML = calls
    .slice(0, 100)
    .map((c, i) => {
      const latencyColor = c.latencyMs > 3000 ? "style='color:var(--warning)'" : "";
      const statusIcon = c.status === "error"
        ? `<span class="status-err">✗</span>`
        : `<span class="status-ok">✓</span>`;

      return `<div class="call-item" onclick="showDetail(${i})">
        <div class="call-top">
          ${providerPill(c.provider)}
          <span class="model-name">${c.model || "?"}</span>
          ${statusIcon}
          <span style="font-size:11px;color:var(--muted)">${fmtTime(c.timestamp)}</span>
        </div>
        <div class="call-meta">
          <span class="call-cost">${fmtCost(c.costUsd)}</span>
          <span ${latencyColor}>${fmt(c.latencyMs)}ms</span>
          <span>${fmt((c.inputTokens || 0) + (c.outputTokens || 0))} tokens</span>
        </div>
        ${c.promptPreview ? `<div class="call-prompt">${c.promptPreview.slice(0, 60).replace(/</g, "&lt;")}</div>` : ""}
      </div>`;
    })
    .join("");
}

// ── Detail ────────────────────────────────────────────────────────────────────

function showDetail(idx) {
  const c = allCalls[idx];
  if (!c) return;

  document.getElementById("calls-tab").style.display = "none";
  const panel = document.getElementById("detail-panel");
  panel.style.display = "block";

  const rows = [
    ["Provider", providerPill(c.provider)],
    ["Model", `<code>${c.model}</code>`],
    ["Status", c.status === "error" ? `<span class="status-err">✗ error</span>` : `<span class="status-ok">✓ success</span>`],
    ["Time", fmtTime(c.timestamp)],
    ["Latency", `${fmt(c.latencyMs)}ms`],
    ["Input tokens", fmt(c.inputTokens || 0)],
    ["Output tokens", fmt(c.outputTokens || 0)],
    ["Cost", `<span style="color:var(--accent2)">${fmtCost(c.costUsd)}</span>`],
  ];

  if (c.errorMessage) {
    rows.push(["Error", `<span style="color:var(--error)">${c.errorMessage.slice(0, 200)}</span>`]);
  }

  let html = rows.map(([k, v]) => `
    <div class="detail-row">
      <span class="detail-key">${k}</span>
      <span class="detail-val">${v}</span>
    </div>`).join("");

  if (c.promptPreview) {
    html += `<div style="margin-top:8px;font-size:11px;color:var(--muted);font-weight:600">PROMPT</div>
      <div class="detail-text">${c.promptPreview.replace(/</g, "&lt;")}</div>`;
  }
  if (c.responsePreview) {
    html += `<div style="margin-top:8px;font-size:11px;color:var(--muted);font-weight:600">RESPONSE</div>
      <div class="detail-text">${c.responsePreview.replace(/</g, "&lt;")}</div>`;
  }

  document.getElementById("detail-content").innerHTML = html;
}

function closeDetail() {
  document.getElementById("detail-panel").style.display = "none";
  document.getElementById("calls-tab").style.display = "";
}

// ── Stats ─────────────────────────────────────────────────────────────────────

function renderStats() {
  chrome.runtime.sendMessage({ type: "get_stats" }, ({ stats }) => {
    const grid = document.getElementById("stats-grid");
    grid.innerHTML = `
      <div class="stat purple"><div class="stat-val">${fmt(stats.totalCalls)}</div><div class="stat-lbl">Calls</div></div>
      <div class="stat green"><div class="stat-val">${fmtCost(stats.totalCost)}</div><div class="stat-lbl">Cost</div></div>
      <div class="stat red"><div class="stat-val">${fmt(stats.errors)}</div><div class="stat-lbl">Errors</div></div>
      <div class="stat"><div class="stat-val">${fmt(stats.totalTokens)}</div><div class="stat-lbl">Tokens</div></div>
      <div class="stat"><div class="stat-val">${fmt(stats.avgLatency)}ms</div><div class="stat-lbl">Avg lat.</div></div>
      <div class="stat"><div class="stat-val">${(stats.byModel || []).length}</div><div class="stat-lbl">Models</div></div>
    `;

    const modelRows = document.getElementById("model-rows");
    if (!stats.byModel?.length) {
      modelRows.innerHTML = "";
      return;
    }
    modelRows.innerHTML = stats.byModel
      .slice(0, 6)
      .map((m) => `
        <div class="model-row">
          <div class="model-info">
            <div class="model-name-sm">${m.model}</div>
            <div class="model-stats">${providerPill(m.provider)} · ${fmt(m.calls)} calls · ${fmt(m.tokens)} tokens</div>
          </div>
          <div class="model-cost">${fmtCost(m.cost)}</div>
        </div>`)
      .join("");
  });
}

// ── Settings ──────────────────────────────────────────────────────────────────

function loadSettings() {
  chrome.runtime.sendMessage({ type: "get_settings" }, ({ settings }) => {
    document.getElementById("s-forward").checked = settings.forwardToServer || false;
    document.getElementById("s-server-url").value = settings.serverUrl || "http://localhost:8765";
    document.getElementById("s-openai").checked = settings.trackOpenAI !== false;
    document.getElementById("s-anthropic").checked = settings.trackAnthropic !== false;
    document.getElementById("s-gemini").checked = settings.trackGemini !== false;
  });
}

function saveSettings() {
  const settings = {
    forwardToServer: document.getElementById("s-forward").checked,
    serverUrl: document.getElementById("s-server-url").value,
    trackOpenAI: document.getElementById("s-openai").checked,
    trackAnthropic: document.getElementById("s-anthropic").checked,
    trackGemini: document.getElementById("s-gemini").checked,
  };
  chrome.runtime.sendMessage({ type: "save_settings", settings });
}

// ── Clear ─────────────────────────────────────────────────────────────────────

function clearCalls() {
  chrome.runtime.sendMessage({ type: "clear_calls" }, () => {
    allCalls = [];
    renderCalls([]);
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

function refresh() {
  chrome.runtime.sendMessage({ type: "get_calls" }, ({ calls }) => {
    allCalls = calls || [];
    if (currentTab === "calls") renderCalls(allCalls);
    if (currentTab === "stats") renderStats();
  });
}

refresh();
setInterval(refresh, 2000);
