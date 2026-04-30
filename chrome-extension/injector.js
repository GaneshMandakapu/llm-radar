/**
 * injector.js — runs in MAIN world, overrides fetch to intercept LLM API calls.
 * Captures request body + response body for OpenAI, Anthropic, Gemini.
 */
(function () {
  const LLM_HOSTS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
  ];

  const PROVIDER_MAP = {
    "api.openai.com": "openai",
    "api.anthropic.com": "anthropic",
    "generativelanguage.googleapis.com": "gemini",
  };

  const PRICING = {
    "gpt-4o": [2.5, 10.0],
    "gpt-4o-mini": [0.15, 0.6],
    "gpt-4-turbo": [10.0, 30.0],
    "gpt-3.5-turbo": [0.5, 1.5],
    "o1": [15.0, 60.0],
    "o3-mini": [1.1, 4.4],
    "claude-opus-4": [15.0, 75.0],
    "claude-sonnet-4": [3.0, 15.0],
    "claude-haiku-4": [0.8, 4.0],
    "claude-3-5-sonnet": [3.0, 15.0],
    "claude-3-5-haiku": [0.8, 4.0],
    "claude-3-opus": [15.0, 75.0],
    "claude-3-haiku": [0.25, 1.25],
    "gemini-2.5-pro": [1.25, 10.0],
    "gemini-2.5-flash": [0.075, 0.3],
    "gemini-1.5-pro": [1.25, 5.0],
    "gemini-1.5-flash": [0.075, 0.3],
  };

  function calcCost(model, inputTokens, outputTokens) {
    const key = Object.keys(PRICING).find((k) => model.toLowerCase().startsWith(k));
    if (!key) return 0;
    const [inCost, outCost] = PRICING[key];
    return (inputTokens * inCost + outputTokens * outCost) / 1_000_000;
  }

  function extractProvider(url) {
    for (const host of LLM_HOSTS) {
      if (url.includes(host)) return PROVIDER_MAP[host];
    }
    return null;
  }

  function extractPromptPreview(body, provider) {
    try {
      const messages = body?.messages;
      if (!messages || !messages.length) return body?.prompt?.slice?.(0, 300) || "";
      const last = [...messages].reverse().find((m) => m.role === "user");
      const content = last?.content;
      if (typeof content === "string") return content.slice(0, 300);
      if (Array.isArray(content)) {
        return content.find((c) => c.type === "text")?.text?.slice(0, 300) || "";
      }
    } catch (_) {}
    return "";
  }

  function parseResponse(provider, data) {
    try {
      if (provider === "openai") {
        const usage = data.usage || {};
        return {
          model: data.model || "unknown",
          inputTokens: usage.prompt_tokens || 0,
          outputTokens: usage.completion_tokens || 0,
          responseText: data.choices?.[0]?.message?.content?.slice(0, 300) || "",
        };
      }
      if (provider === "anthropic") {
        const usage = data.usage || {};
        return {
          model: data.model || "unknown",
          inputTokens: usage.input_tokens || 0,
          outputTokens: usage.output_tokens || 0,
          responseText: data.content?.[0]?.text?.slice(0, 300) || "",
        };
      }
      if (provider === "gemini") {
        const usage = data.usageMetadata || {};
        const modelName = data.modelVersion || "gemini-unknown";
        return {
          model: modelName,
          inputTokens: usage.promptTokenCount || 0,
          outputTokens: usage.candidatesTokenCount || 0,
          responseText: data.candidates?.[0]?.content?.parts?.[0]?.text?.slice(0, 300) || "",
        };
      }
    } catch (_) {}
    return { model: "unknown", inputTokens: 0, outputTokens: 0, responseText: "" };
  }

  const origFetch = window.fetch;
  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : input?.url || "";
    const provider = extractProvider(url);

    if (!provider) return origFetch.apply(this, arguments);

    let reqBody = null;
    try {
      const bodyStr = init?.body || (input instanceof Request ? await input.clone().text() : "");
      reqBody = JSON.parse(bodyStr);
    } catch (_) {}

    const promptPreview = extractPromptPreview(reqBody, provider);
    const start = performance.now();

    try {
      const response = await origFetch.apply(this, arguments);
      const latencyMs = performance.now() - start;
      const clone = response.clone();

      clone.json().then((data) => {
        const parsed = parseResponse(provider, data);
        const model = reqBody?.model || parsed.model;
        const cost = calcCost(model, parsed.inputTokens, parsed.outputTokens);

        window.dispatchEvent(
          new CustomEvent("__llm_radar_call__", {
            detail: {
              provider,
              model,
              inputTokens: parsed.inputTokens,
              outputTokens: parsed.outputTokens,
              costUsd: cost,
              latencyMs: Math.round(latencyMs),
              status: "success",
              promptPreview,
              responsePreview: parsed.responseText,
              timestamp: Date.now(),
            },
          })
        );
      }).catch(() => {});

      return response;
    } catch (err) {
      const latencyMs = performance.now() - start;
      window.dispatchEvent(
        new CustomEvent("__llm_radar_call__", {
          detail: {
            provider,
            model: reqBody?.model || "unknown",
            inputTokens: 0,
            outputTokens: 0,
            costUsd: 0,
            latencyMs: Math.round(latencyMs),
            status: "error",
            errorMessage: err.message,
            promptPreview,
            responsePreview: null,
            timestamp: Date.now(),
          },
        })
      );
      throw err;
    }
  };

  // Forward events to content script world for storage
  window.addEventListener("__llm_radar_call__", (e) => {
    window.postMessage({ type: "__llm_radar_call__", detail: e.detail }, "*");
  });
})();
