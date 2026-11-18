// Phase 3 · D3: the service worker's part of a check, with the browser and the SAVIO host faked.
// The fake host finds a PAN (ABCPE1234F) in text and in "documents" whose base64 decodes to one.
import { test } from "node:test";
import assert from "node:assert/strict";

const PAN = /[A-Z]{5}[0-9]{4}[A-Z]/g;
let managed = {};
const asked = [];
let onMessage;
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
      return { ok: true };
    },
  },
  storage: {
    managed: { get: async () => managed },
    onChanged: { addListener() {} },
    local: { get: async () => ({}), set: async () => {} },
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
