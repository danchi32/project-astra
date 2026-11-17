// Phase 3 · D3: the extension's service worker. Content scripts send it the text a person is
// about to paste, drop, upload or submit. It asks the local SAVIO host to scan it, decides
// per the org's policy, and answers allow / warn / block.
//
// The text goes only to the native host on this PC (com.savio.guard), never to a server. What
// is kept is counts only: the last 200 decisions, for the E3 ledger the agent will read.
import { decide, isWatched, readPolicy } from "./decide.js";

const HOST = "com.savio.guard";
const MAX_EVENTS = 200;

async function policy() {
  try {
    // Set by the org through browser policy (3rdparty/extensions/<id>/policy), written by the agent.
    return readPolicy(await chrome.storage.managed.get(null));
  } catch {
    return readPolicy(null);
  }
}

async function scan(text, keywords) {
  try {
    return await chrome.runtime.sendNativeMessage(HOST, { type: "scan", text, keywords });
  } catch {
    return null; // host not installed or not running: decide() treats this as "could not check"
  }
}

async function record(event) {
  try {
    const { events = [] } = await chrome.storage.local.get("events");
    events.push(event);
    await chrome.storage.local.set({ events: events.slice(-MAX_EVENTS) });
  } catch {
    // The ledger is best-effort; the decision already stands.
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type !== "check" || typeof msg.text !== "string") return false;
  (async () => {
    const p = await policy();
    const host = (() => { try { return new URL(sender.url ?? "").hostname; } catch { return ""; } })();
    if (!isWatched(p, host)) return sendResponse({ action: "allow", findings: [] });
    const result = decide(p, await scan(msg.text, p.keywords));
    await record({ at: new Date().toISOString(), site: host, kind: msg.kind, mode: p.mode,
                   action: result.action, findings: result.findings, unknown: result.unknown });
    sendResponse(result);
  })();
  return true; // the answer comes asynchronously
});
