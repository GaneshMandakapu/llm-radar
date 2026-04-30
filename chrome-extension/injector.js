/**
 * injector.js — MAIN world fetch interceptor.
 * Handles direct LLM API calls AND chat app streaming endpoints.
 * Uses stream tee() so original response is never broken.
 */
(function () {
  const PRICING = {
    "gpt-4o": [2.5, 10.0], "gpt-4o-mini": [0.15, 0.6],
    "gpt-4-turbo": [10.0, 30.0], "gpt-3.5-turbo": [0.5, 1.5],
    "o1": [15.0, 60.0], "o3-mini": [1.1, 4.4], "o4-mini": [1.1, 4.4],
    "claude-opus-4": [15.0, 75.0], "claude-sonnet-4": [3.0, 15.0],
    "claude-haiku-4": [0.8, 4.0], "claude-3-5-sonnet": [3.0, 15.0],
    "claude-3-5-haiku": [0.8, 4.0], "claude-3-opus": [15.0, 75.0],
    "claude-3-haiku": [0.25, 1.25],
    "gemini-2.5-pro": [1.25, 10.0], "gemini-2.5-flash": [0.075, 0.3],
    "gemini-1.5-pro": [1.25, 5.0], "gemini-1.5-flash": [0.075, 0.3],
  };

  function calcCost(model, inp, out) {
    const m = (model || "").toLowerCase();
    const key = Object.keys(PRICING).find(k => m.startsWith(k) || m.includes(k));
    if (!key) return 0;
    return (inp * PRICING[key][0] + out * PRICING[key][1]) / 1_000_000;
  }

  // ── Endpoint registry ────────────────────────────────────────────────────
  // Each entry: { match(url) → bool, provider, format }
  const ENDPOINTS = [
    // Direct APIs
    {
      match: u => u.includes("api.openai.com/v1/chat"),
      provider: "openai", format: "openai_direct",
    },
    {
      match: u => u.includes("api.anthropic.com/v1/messages"),
      provider: "anthropic", format: "anthropic_direct",
    },
    {
      match: u => u.includes("generativelanguage.googleapis.com"),
      provider: "gemini", format: "gemini_direct",
    },
    // ChatGPT web app
    {
      match: u => (u.includes("chatgpt.com") || u.includes("chat.openai.com")) && u.includes("conversation"),
      provider: "openai", format: "chatgpt_stream",
    },
    // Claude.ai web app
    {
      match: u => u.includes("claude.ai") && (u.includes("completion") || u.includes("messages")),
      provider: "anthropic", format: "claude_ai_stream",
    },
    // Gemini web app (aistudio, gemini.google.com)
    {
      match: u => (u.includes("gemini.google.com") || u.includes("aistudio.google.com")) && u.includes("generate"),
      provider: "gemini", format: "gemini_stream",
    },
  ];

  function detectEndpoint(url) {
    return ENDPOINTS.find(e => e.match(url)) || null;
  }

  // ── Prompt extraction ────────────────────────────────────────────────────
  function extractPrompt(body, format) {
    try {
      const messages = body?.messages;
      if (messages?.length) {
        const last = [...messages].reverse().find(m => m.role === "user");
        const c = last?.content;
        if (typeof c === "string") return c.slice(0, 400);
        if (Array.isArray(c)) return (c.find(x => x.type === "text")?.text || "").slice(0, 400);
      }
      if (body?.prompt) return String(body.prompt).slice(0, 400);
    } catch (_) {}
    return "";
  }

  // ── JSON response parsers ────────────────────────────────────────────────
  function parseOpenAIDirect(data, reqBody) {
    const usage = data.usage || {};
    return {
      model: data.model || reqBody?.model || "gpt-unknown",
      inputTokens: usage.prompt_tokens || 0,
      outputTokens: usage.completion_tokens || 0,
      responseText: data.choices?.[0]?.message?.content?.slice(0, 300) || "",
    };
  }

  function parseAnthropicDirect(data, reqBody) {
    const usage = data.usage || {};
    return {
      model: data.model || reqBody?.model || "claude-unknown",
      inputTokens: usage.input_tokens || 0,
      outputTokens: usage.output_tokens || 0,
      responseText: data.content?.[0]?.text?.slice(0, 300) || "",
    };
  }

  function parseGeminiDirect(data, url) {
    const usage = data.usageMetadata || {};
    const modelMatch = url.match(/models\/([^/:?]+)/);
    return {
      model: modelMatch?.[1] || "gemini-unknown",
      inputTokens: usage.promptTokenCount || 0,
      outputTokens: usage.candidatesTokenCount || 0,
      responseText: data.candidates?.[0]?.content?.parts?.[0]?.text?.slice(0, 300) || "",
    };
  }

  // ── SSE stream parser ────────────────────────────────────────────────────
  async function consumeSSE(stream, format, reqBody, url) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let model = reqBody?.model || "unknown";
    let inputTokens = 0, outputTokens = 0;
    let responseText = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep incomplete line

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const raw = line.slice(5).trim();
          if (raw === "[DONE]") continue;
          try {
            const obj = JSON.parse(raw);

            if (format === "chatgpt_stream") {
              // ChatGPT SSE: {message: {author, content: {parts:[...]}}, ...}
              const m = obj.message;
              if (m?.author?.role === "assistant") {
                const parts = m.content?.parts;
                if (parts?.length) responseText = parts.join("").slice(0, 300);
              }
              // Model in metadata
              if (obj.metadata?.model_slug) model = obj.metadata.model_slug;
              // Token usage in final chunk
              if (obj.usage_metadata || obj.message?.metadata?.finish_details) {
                const u = obj.usage_metadata || {};
                inputTokens = u.input_tokens || inputTokens;
                outputTokens = u.output_tokens || outputTokens;
              }

            } else if (format === "claude_ai_stream") {
              // Claude.ai SSE: anthropic event format
              if (obj.type === "content_block_delta") {
                responseText += (obj.delta?.text || "");
              }
              if (obj.type === "message_start") {
                model = obj.message?.model || model;
                inputTokens = obj.message?.usage?.input_tokens || 0;
              }
              if (obj.type === "message_delta") {
                outputTokens = obj.usage?.output_tokens || 0;
              }

            } else if (format === "gemini_stream") {
              // Gemini SSE
              const candidate = obj.candidates?.[0];
              if (candidate?.content?.parts?.[0]?.text) {
                responseText += candidate.content.parts[0].text;
              }
              const u = obj.usageMetadata || {};
              if (u.promptTokenCount) inputTokens = u.promptTokenCount;
              if (u.candidatesTokenCount) outputTokens = u.candidatesTokenCount;
              model = obj.modelVersion || model;

            } else {
              // Generic OpenAI streaming format (delta chunks)
              const delta = obj.choices?.[0]?.delta?.content;
              if (delta) responseText += delta;
              if (obj.model) model = obj.model;
              const u = obj.usage || {};
              if (u.prompt_tokens) inputTokens = u.prompt_tokens;
              if (u.completion_tokens) outputTokens = u.completion_tokens;
            }
          } catch (_) {}
        }
      }
    } catch (_) {}

    // Estimate tokens from text if API didn't provide them
    if (!outputTokens && responseText) outputTokens = Math.ceil(responseText.length / 4);
    if (!inputTokens && reqBody) {
      const promptText = extractPrompt(reqBody, format);
      inputTokens = Math.ceil(promptText.length / 4);
    }

    return { model, inputTokens, outputTokens, responseText: responseText.slice(0, 300) };
  }

  // ── Main fetch override ──────────────────────────────────────────────────
  const origFetch = window.fetch;
  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : (input?.url || "");
    const endpoint = detectEndpoint(url);
    if (!endpoint) return origFetch.apply(this, arguments);

    let reqBody = null;
    try {
      const bodyStr = init?.body || (input instanceof Request ? await input.clone().text() : "");
      reqBody = typeof bodyStr === "string" ? JSON.parse(bodyStr) : bodyStr;
    } catch (_) {}

    const promptPreview = extractPrompt(reqBody, endpoint.format);
    const start = performance.now();

    try {
      const response = await origFetch.apply(this, arguments);
      const latencyMs = Math.round(performance.now() - start);
      const contentType = response.headers.get("content-type") || "";
      const isStream = contentType.includes("text/event-stream") || contentType.includes("stream");

      if (isStream && response.body) {
        // Tee the stream — original goes to page, clone goes to us
        const [pageStream, monitorStream] = response.body.tee();

        consumeSSE(monitorStream, endpoint.format, reqBody, url).then(({ model, inputTokens, outputTokens, responseText }) => {
          const cost = calcCost(model, inputTokens, outputTokens);
          emit({
            provider: endpoint.provider, model,
            inputTokens, outputTokens, costUsd: cost,
            latencyMs, status: "success",
            promptPreview, responsePreview: responseText,
            timestamp: Date.now(),
          });
        });

        return new Response(pageStream, {
          status: response.status,
          statusText: response.statusText,
          headers: response.headers,
        });

      } else {
        // Non-streaming — clone + parse JSON
        const clone = response.clone();
        clone.json().then(data => {
          let parsed = { model: "unknown", inputTokens: 0, outputTokens: 0, responseText: "" };
          if (endpoint.format === "openai_direct") parsed = parseOpenAIDirect(data, reqBody);
          else if (endpoint.format === "anthropic_direct") parsed = parseAnthropicDirect(data, reqBody);
          else if (endpoint.format === "gemini_direct") parsed = parseGeminiDirect(data, url);

          const cost = calcCost(parsed.model, parsed.inputTokens, parsed.outputTokens);
          emit({
            provider: endpoint.provider, model: parsed.model,
            inputTokens: parsed.inputTokens, outputTokens: parsed.outputTokens,
            costUsd: cost, latencyMs, status: "success",
            promptPreview, responsePreview: parsed.responseText,
            timestamp: Date.now(),
          });
        }).catch(() => {});

        return response;
      }

    } catch (err) {
      const latencyMs = Math.round(performance.now() - start);
      emit({
        provider: endpoint.provider,
        model: reqBody?.model || "unknown",
        inputTokens: 0, outputTokens: 0, costUsd: 0,
        latencyMs, status: "error",
        errorMessage: err.message,
        promptPreview, responsePreview: null,
        timestamp: Date.now(),
      });
      throw err;
    }
  };

  function emit(detail) {
    window.postMessage({ type: "__llm_radar_call__", detail }, "*");
  }

  window.addEventListener("__llm_radar_call__", e => {
    window.postMessage({ type: "__llm_radar_call__", detail: e.detail }, "*");
  });
})();
