// Phase 3 · D3: the extension's service worker. Content scripts send it the text a person is
// about to paste, drop, upload or submit. It asks the local SAVIO host to scan it, decides
// per the org's policy, and answers allow / warn / block.
//
// The text goes only to the native host on this PC (com.savio.guard), never to a server.
// E3: when something was found (or could not be checked), the event (counts only, in the fixed
// shape the agent accepts) goes back through the host to the SAVIO service, which sends it on
// to the org's portal. A local copy of the last 200 is kept here as well.
import {
  DOWNLOAD_DAYS, MAX_DOWNLOADS, REASONS, decide, downloadOrigin, fromHost, hostOf, isWatched, mergeScans, originFor,
  readPolicy, toEvent, withOutcome,
} from "./decide.js";
import { accountRules } from "./accounts.js";

const HOST = "com.savio.guard";
const MAX_EVENTS = 200;

// D2: the company-account headers follow the managed settings: set at start, replaced whenever
// the org's policy changes, and removed when it no longer asks for them.
async function syncAccounts() {
  let managed = null;
  try { managed = await chrome.storage.managed.get(null); } catch { /* no policy: no rules */ }
  try {
    const old = (await chrome.declarativeNetRequest.getDynamicRules()).map((r) => r.id);
    await chrome.declarativeNetRequest.updateDynamicRules({ removeRuleIds: old, addRules: accountRules(managed) });
  } catch {
    // Rules stay as they were; the next start or policy change tries again.
  }
}
chrome.runtime.onStartup.addListener(syncAccounts);
chrome.runtime.onInstalled.addListener(syncAccounts);
chrome.storage.onChanged.addListener((_, area) => { if (area === "managed") syncAccounts(); });

// C2: where files came from. Each finished download's name, size and site are kept here, in the
// browser's own local storage (the browser keeps its download history anyway), for 30 days, at
// most 500. When a file is uploaded, dropped or pasted, only the matching site goes into the
// event, never the file's name.
chrome.downloads?.onChanged.addListener(async (delta) => {
  if (delta.state?.current !== "complete") return;
  try {
    const [item] = await chrome.downloads.search({ id: delta.id });
    const origin = downloadOrigin(item);
    if (!item || !origin) return;
    const name = String(item.filename ?? "").split(/[\\/]/).pop();
    const { downloads = [] } = await chrome.storage.local.get("downloads");
    const since = Date.now() - DOWNLOAD_DAYS * 86_400_000;
    downloads.push({ name, size: item.fileSize, origin, at: Date.now() });
    await chrome.storage.local.set({ downloads: downloads.filter((d) => d.at >= since).slice(-MAX_DOWNLOADS) });
  } catch {
    // Without it the event simply has no origin.
  }
});

async function fileOrigin(files) {
  if (!Array.isArray(files) || !files.length) return null;
  const meta = files.slice(0, 20).filter((f) => typeof f?.name === "string" && f.name.length <= 255 && Number.isInteger(f?.size));
  try {
    return originFor(meta, (await chrome.storage.local.get("downloads")).downloads);
  } catch {
    return null;
  }
}

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

// A Word, Excel or PDF file being uploaded, as base64: the host reads and scans it on this PC and
// answers with counts. One it cannot read is "could not check".
async function scanFile(doc, keywords) {
  try {
    return fromHost(await chrome.runtime.sendNativeMessage(HOST, { type: "scan_file", name: doc.name, data: doc.data, keywords }));
  } catch {
    return null;
  }
}

async function redact(text, keywords, keep) {
  try {
    const r = await chrome.runtime.sendNativeMessage(HOST, { type: "redact", text, keywords, keep });
    return r?.ok === true && typeof r.redacted === "string" ? r.redacted : null;
  } catch {
    return null;
  }
}

async function approved(site, channel) {
  try {
    const r = await chrome.runtime.sendNativeMessage(HOST, { type: "approved", site, channel });
    return r?.ok === true && r.approved === true;
  } catch {
    return false;
  }
}

async function record(event) {
  try {
    const r = await chrome.runtime.sendNativeMessage(HOST, { type: "event", event });
    if (r?.ok === false && r.error === "malformed event" && event.origin) {
      // A SAVIO agent from before C2 refuses the field: the event still counts without it.
      const { origin, ...older } = event;
      await chrome.runtime.sendNativeMessage(HOST, { type: "event", event: older });
    }
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

// Security review M5: an event waiting for the person's answer stays here, in session storage
// (it outlives the service worker going to sleep), under a random id. The page side only ever
// sends back that id, which is taken once; it cannot change what was found or where.
async function hold(event) {
  const id = crypto.randomUUID();
  await chrome.storage.session.set({ ["pending:" + id]: event });
  return id;
}

async function release(id) {
  if (typeof id !== "string" || !/^[0-9a-f-]{36}$/.test(id)) return null;
  const key = "pending:" + id;
  const { [key]: event } = await chrome.storage.session.get(key);
  await chrome.storage.session.remove(key);
  return event ?? null;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // Only this extension's own content scripts can reach here; a web page cannot.
  if (sender.id !== chrome.runtime.id) return false;

  if (msg?.type === "outcome") {
    // D7: the person answered a prompt. Recorded once, with the answer.
    release(msg.id).then((held) => {
      const event = withOutcome(held, msg.outcome, msg.reason);
      if (event) record(event);
    });
    return false;
  }
  if (msg?.type !== "check" || typeof msg.text !== "string") return false;
  (async () => {
    const p = await policy();
    // The page's own origin: about:blank, srcdoc and blob frames carry their creator's (H3).
    const host = hostOf(sender.origin && sender.origin !== "null" ? sender.origin : sender.url ?? sender.tab?.url);
    if (!isWatched(p, host)) return sendResponse({ action: "allow", findings: [] });
    // Files the content script could not read (binary, too big) make the check "unknown":
    // never silently clean (M3).
    const unreadable = Number.isInteger(msg.unreadable) && msg.unreadable > 0;
    // `parts`: the form fields or text files that can be rewritten; `text` and `docs` are the
    // rest. Without `parts`, all of `text` is one rewritable whole (a paste).
    const parts = Array.isArray(msg.parts) ? msg.parts.filter((s) => typeof s === "string").slice(0, 200) : null;
    const docs = Array.isArray(msg.docs)
      ? msg.docs.filter((d) => typeof d?.name === "string" && typeof d?.data === "string").slice(0, 10) : [];
    let scanned = null;
    let fixed;
    if (!unreadable) {
      fixed = await scan(msg.text, p.keywords);
      for (const d of docs) fixed = mergeScans(fixed, await scanFile(d, p.keywords));
      scanned = parts?.length ? mergeScans(fixed, await scan(parts.join("\n"), p.keywords)) : fixed;
    }
    let result = decide(p, scanned, msg.kind, parts || docs.length ? fixed : undefined);
    if (result.action === "redact" && parts) {
      // Each field or file back from the host with findings replaced. If it cannot vouch for one,
      // ask the person rather than send something unchecked.
      const redactedParts = await Promise.all(parts.map((t) => redact(t, p.keywords, p.ignoreKinds)));
      result = redactedParts.includes(null) ? { ...result, action: "warn" } : { ...result, redactedParts };
    } else if (result.action === "redact" && msg.kind === "paste") {
      // The same text back from the host with findings replaced; if it cannot vouch for the
      // result, fall back to asking the person rather than pasting something unchecked.
      const redacted = await redact(msg.text, p.keywords, p.ignoreKinds);
      result = redacted === null ? { ...result, action: "warn" } : { ...result, redacted };
    } else if (result.action === "redact") {
      // A form or file sent without its parts (the page's copy of the mode was behind the
      // policy's): nothing to rewrite, so the person is asked.
      result = { ...result, action: "warn" };
    }
    const event = toEvent(p, host, msg.kind, scanned, result, await fileOrigin(msg.files));
    if (event && result.action === "approve" && await approved(host, msg.kind)) {
      // IT approved this person, site and channel for now: through, and recorded as such.
      sendResponse({ ...result, action: "allow" });
      return record({ ...event, outcome: "proceeded" });
    }
    if (event && ["warn", "justify", "approve"].includes(result.action)) {
      // Held until the person answers; the content script sends back only the id.
      return sendResponse({ ...result, pending: await hold(event), reasons: result.action === "justify" ? REASONS : undefined });
    }
    sendResponse(result);                       // the person is not kept waiting for the record
    if (event) await record(event);
  })();
  return true; // the answer comes asynchronously
});
