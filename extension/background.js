// Phase 3 · D3: the extension's service worker. Content scripts send it the text a person is
// about to paste, drop, upload or submit. It asks the local SAVIO host to scan it, decides
// per the org's policy, and answers allow / warn / block.
//
// The text goes only to the native host on this PC (com.savio.guard), never to a server.
// E3: when something was found (or could not be checked), the event (counts only, in the fixed
// shape the agent accepts) goes back through the host to the SAVIO service, which sends it on
// to the org's portal. A local copy of the last 200 is kept here as well.
import { decide, fromHost, isWatched, readPolicy, toEvent } from "./decide.js";

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
    return fromHost(await chrome.runtime.sendNativeMessage(HOST, { type: "scan", text, keywords }));
  } catch {
    return null; // host not installed or not running: decide() treats this as "could not check"
  }
}

async function record(event) {
  try {
    await chrome.runtime.sendNativeMessage(HOST, { type: "event", event });
  } catch {
    // The service is not reachable; the local copy below still has it.
  }
  try {
    const { events = [] } = await chrome.storage.local.get("events");
    events.push({ at: new Date().toISOString(), ...event });
    await chrome.storage.local.set({ events: events.slice(-MAX_EVENTS) });
  } catch {
    // Best-effort; the decision already stands.
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type !== "check" || typeof msg.text !== "string") return false;
  (async () => {
    const p = await policy();
    const host = (() => { try { return new URL(sender.url ?? "").hostname; } catch { return ""; } })();
    if (!isWatched(p, host)) return sendResponse({ action: "allow", findings: [] });
    const scanned = await scan(msg.text, p.keywords);
    const result = decide(p, scanned);
    sendResponse(result);                       // the person is not kept waiting for the record
    const event = toEvent(p, host, msg.kind, scanned, result);
    if (event) await record(event);
  })();
  return true; // the answer comes asynchronously
});
