/**
 * content.js — bridges MAIN world events → background service worker.
 * Listens for postMessage from injector.js, forwards via chrome.runtime.sendMessage.
 */
window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  if (event.data?.type !== "__llm_radar_call__") return;

  const call = event.data.detail;
  if (!call) return;

  chrome.runtime.sendMessage({ type: "llm_radar_call", call });
});
