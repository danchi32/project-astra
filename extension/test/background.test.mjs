// Phase 3 · D3: the service worker's part of a check, with the browser and the SAVIO host faked.
// The fake host finds a PAN (ABCPE1234F) in text and in "documents" whose base64 decodes to one.
import { test } from "node:test";
import assert from "node:assert/strict";

const PAN = /[A-Z]{5}[0-9]{4}[A-Z]/g;
let managed = {};
const asked = [];
const sent = [];          // events the host was handed
let oldAgent = false;     // a host from before C2 refuses an event with an origin
let onMessage;
let onDownload;
const local = {};
const downloadItems = {};
const scanOf = (text) => ({ ok: true, counts: (text.match(PAN) ?? []).length ? { Pan: text.match(PAN).length } : {} });

globalThis.chrome = {
  runtime: {
    id: "savio",
    onStartup: { addListener() {} }, onInstalled: { addListener() {} },
    onMessage: { addListener(f) { onMessage = f; } },
    async sendNativeMessage(_host, req) {
      asked.push(req.type);
      if (req.type === "scan") return scanOf(req.text);
      if (req.type === "redact") return { ok: true, redacted: req.text.replace(PAN, "[PAN]") };
      if (req.type === "scan_file") {
        const text = Buffer.from(req.data, "base64").toString();
        return text.startsWith("DOC:") ? scanOf(text) : { ok: false, error: "could not read the document" };
      }
      if (req.type === "event") {
        if (oldAgent && "origin" in req.event) return { ok: false, error: "malformed event" };
        sent.push(req.event);
      }
      return { ok: true };
    },
  },
  downloads: {
    onChanged: { addListener(f) { onDownload = f; } },
    search: async ({ id }) => [downloadItems[id]],
  },
  storage: {
    managed: { get: async () => managed },
    onChanged: { addListener() {} },
    local: { get: async (k) => (k in local ? { [k]: local[k] } : {}), set: async (o) => Object.assign(local, o) },
    session: { set: async () => {}, get: async () => ({}), remove: async () => {} },
  },
  declarativeNetRequest: { getDynamicRules: async () => [], updateDynamicRules: async () => {} },
};
await import("../background.js");

const check = (msg) => new Promise((resolve) =>
  onMessage({ type: "check", ...msg }, { id: "savio", origin: "https://chatgpt.com" }, resolve));
const doc = (text) => ({ name: "a.pdf", data: Buffer.from(text).toString("base64") });

test("redact rewrites each form field or text file, and only when the rest is clean", async () => {
  managed = { mode: "redact" };
  const r = await check({ kind: "submit", text: "India", parts: ["PAN ABCPE1234F", "hello"] });
  assert.equal(r.action, "redact");
  assert.deepEqual(r.redactedParts, ["PAN [PAN]", "hello"]);

  // A PAN in a field that cannot be rewritten (a select, a hidden field): asked, not "hidden".
  assert.equal((await check({ kind: "submit", text: "ABCPE1234F", parts: ["PAN ABCPE1234F"] })).action, "warn");
  // A PAN inside a PDF next to a text file: the PDF cannot be changed, so asked.
  assert.equal((await check({ kind: "file", text: "", parts: ["ok"], docs: [doc("DOC: ABCPE1234F")] })).action, "warn");
  // The text file has it, the PDF is clean: the text file is rewritten.
  const f = await check({ kind: "file", text: "", parts: ["ABCPE1234F"], docs: [doc("DOC: nothing")] });
  assert.deepEqual([f.action, f.redactedParts], ["redact", ["[PAN]"]]);
  // A form sent without its parts (the page's mode was behind): nothing to rewrite, so asked.
  assert.equal((await check({ kind: "submit", text: "PAN ABCPE1234F" })).action, "warn");
  // A paste is still rewritten whole.
  assert.equal((await check({ kind: "paste", text: "PAN ABCPE1234F" })).redacted, "PAN [PAN]");
});

test("an upload of a file downloaded earlier carries where it came from, and only that", async () => {
  managed = { mode: "log" };
  downloadItems[7] = { id: 7, filename: "C:\\Users\\ravi\\Downloads\\clients.csv", fileSize: 40,
                       finalUrl: "https://crm.zoho.com/export?all=1" };
  await onDownload({ id: 7, state: { current: "complete" } });
  assert.deepEqual(local.downloads.map((d) => [d.name, d.size, d.origin]), [["clients.csv", 40, "crm.zoho.com"]]);

  sent.length = 0;
  await check({ kind: "file", text: "ABCPE1234F", files: [{ name: "clients.csv", size: 40 }] });
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(sent.at(-1).origin, "crm.zoho.com");
  assert.equal(JSON.stringify(sent.at(-1)).includes("clients.csv"), false);   // the name never leaves

  // A SAVIO agent from before C2: the event is sent again without the field, and still counts.
  oldAgent = true;
  await check({ kind: "file", text: "ABCPE1234F", files: [{ name: "clients.csv", size: 40 }] });
  await new Promise((r) => setTimeout(r, 10));
  oldAgent = false;
  assert.equal("origin" in sent.at(-1), false);
});

test("documents are read by the host; one it cannot read is 'could not check'", async () => {
  managed = { mode: "block" };
  assert.equal((await check({ kind: "file", text: "", docs: [doc("DOC: ABCPE1234F")] })).action, "block");
  assert.equal((await check({ kind: "file", text: "", docs: [doc("DOC: nothing")] })).action, "allow");
  const broken = await check({ kind: "file", text: "", docs: [doc("garbage")] });
  assert.deepEqual([broken.action, broken.unknown], ["warn", true]);
  asked.length = 0;
  await check({ kind: "file", text: "", unreadable: 1, docs: [doc("DOC: x")] });
  assert.deepEqual(asked.filter((t) => t.startsWith("scan")), []);   // already unknown: nothing sent to the host
});

test("more documents or parts than are scanned is 'could not check', not the first ones for all (review H2)", async () => {
  managed = { mode: "block" };
  const docs = [...Array(10).fill(doc("DOC: nothing")), doc("DOC: ABCPE1234F")];
  const r = await check({ kind: "file", text: "", docs });
  assert.deepEqual([r.action, r.unknown], ["warn", true]);
  const parts = await check({ kind: "file", text: "", parts: Array(201).fill("ok") });
  assert.equal(parts.unknown, true);
});
