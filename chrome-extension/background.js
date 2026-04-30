/**
 * background.js — MV3 service worker.
 * Receives LLM call data from content scripts, stores in chrome.storage.local.
 * Optionally forwards to local llm-radar server.
 */

const MAX_CALLS = 500;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "llm_radar_call") {
    storeCall(msg.call).then(() => sendResponse({ ok: true }));
    return true; // keep channel open for async
  }

  if (msg.type === "get_calls") {
    chrome.storage.local.get(["llm_calls"], (result) => {
      sendResponse({ calls: result.llm_calls || [] });
    });
    return true;
  }

  if (msg.type === "get_stats") {
    chrome.storage.local.get(["llm_calls"], (result) => {
      sendResponse({ stats: computeStats(result.llm_calls || []) });
    });
    return true;
  }

  if (msg.type === "clear_calls") {
    chrome.storage.local.set({ llm_calls: [] }, () => sendResponse({ ok: true }));
    return true;
  }

  if (msg.type === "get_settings") {
    chrome.storage.local.get(["llm_radar_settings"], (result) => {
      sendResponse({ settings: result.llm_radar_settings || defaultSettings() });
    });
    return true;
  }

  if (msg.type === "save_settings") {
    chrome.storage.local.set({ llm_radar_settings: msg.settings }, () =>
      sendResponse({ ok: true })
    );
    return true;
  }
});

async function storeCall(call) {
  return new Promise((resolve) => {
    chrome.storage.local.get(["llm_calls", "llm_radar_settings"], (result) => {
      const calls = result.llm_calls || [];
      const settings = result.llm_radar_settings || defaultSettings();

      calls.unshift(call); // newest first
      if (calls.length > MAX_CALLS) calls.splice(MAX_CALLS);

      chrome.storage.local.set({ llm_calls: calls }, resolve);

      // Forward to local server if enabled
      if (settings.forwardToServer && settings.serverUrl) {
        fetch(settings.serverUrl + "/api/ingest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(call),
        }).catch(() => {});
      }
    });
  });
}

function computeStats(calls) {
  const totalCalls = calls.length;
  const totalTokens = calls.reduce((s, c) => s + (c.inputTokens || 0) + (c.outputTokens || 0), 0);
  const totalCost = calls.reduce((s, c) => s + (c.costUsd || 0), 0);
  const errors = calls.filter((c) => c.status === "error").length;
  const avgLatency =
    totalCalls > 0
      ? calls.reduce((s, c) => s + (c.latencyMs || 0), 0) / totalCalls
      : 0;

  const byModel = {};
  for (const c of calls) {
    const key = `${c.provider}/${c.model}`;
    if (!byModel[key]) byModel[key] = { provider: c.provider, model: c.model, calls: 0, cost: 0, tokens: 0 };
    byModel[key].calls++;
    byModel[key].cost += c.costUsd || 0;
    byModel[key].tokens += (c.inputTokens || 0) + (c.outputTokens || 0);
  }

  return {
    totalCalls,
    totalTokens,
    totalCost,
    errors,
    avgLatency: Math.round(avgLatency),
    byModel: Object.values(byModel).sort((a, b) => b.calls - a.calls),
  };
}

function defaultSettings() {
  return {
    forwardToServer: false,
    serverUrl: "http://localhost:8765",
    trackOpenAI: true,
    trackAnthropic: true,
    trackGemini: true,
  };
}
