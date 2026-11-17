// Phase 3 · D3: watches the four ways text leaves a page: paste, drop, file upload and form
// submit. Listeners run in the capture phase on the document, before the site's own handlers.
//
// In "log" mode nothing is held up: the content is checked afterwards and only the counts are
// recorded. In "warn" / "justify" / "block" mode the action is held, checked by the local
// scanner (a few milliseconds), then carried out, confirmed or refused in SAVIO's own prompt
// (dialog.js, D7). The answer to a warn or justify prompt goes back with the event.
(() => {
  const MAX_FILE_BYTES = 5 * 1024 * 1024;
  const TEXT_FILE = /\.(txt|csv|tsv|json|md|xml|log|html?)$/i;
  let mode = "log";
  let resubmitting = false;

  chrome.storage.managed.get("mode")
    .then((m) => { if (m && ["log", "warn", "justify", "redact", "approve", "block"].includes(m.mode)) mode = m.mode; })
    .catch(() => {});

  const check = (kind, text) => chrome.runtime.sendMessage({ type: "check", kind, text })
    .catch(() => ({ action: "warn", unknown: true }));

  // The text to go ahead with (the original, or with the sensitive parts hidden), or null.
  async function handled(kind, text) {
    const r = await check(kind, text);
    if (r.action === "allow") return text;
    if (r.action === "redact" && typeof r.redacted === "string") {
      globalThis.__savioGuardNotice("hidden", r.reason);
      return r.redacted;
    }
    const answer = await globalThis.__savioGuardDialog(kind, r);
    if (r.event) {
      chrome.runtime.sendMessage({ type: "outcome", event: r.event, outcome: answer.outcome, reason: answer.reason })
        .catch(() => {});
    }
    if (answer.outcome === "requested") globalThis.__savioGuardNotice("asked", null, kind);
    return ["warn", "justify"].includes(r.action) && answer.outcome === "proceeded" ? text : null;
  }
  const allowed = async (kind, text) => (await handled(kind, text)) !== null;

  function insert(target, text) {
    target?.focus?.();
    document.execCommand("insertText", false, text);
  }

  document.addEventListener("paste", (e) => {
    const text = e.clipboardData?.getData("text/plain") ?? "";
    if (text.length < 8) return;
    if (mode === "log") { check("paste", text); return; }
    e.preventDefault();
    e.stopImmediatePropagation();
    const target = e.target;
    handled("paste", text).then((out) => out !== null && insert(target, out));
  }, true);

  async function filesText(files) {
    const parts = [];
    for (const f of files) {
      if (f.size <= MAX_FILE_BYTES && (f.type.startsWith("text/") || TEXT_FILE.test(f.name))) parts.push(await f.text());
    }
    return parts.join("\n");
  }

  document.addEventListener("drop", async (e) => {
    const dt = e.dataTransfer;
    if (!dt) return;
    const files = [...(dt.files ?? [])];
    const text = dt.getData("text/plain") || "";
    if (mode === "log") { check("drop", text + "\n" + (await filesText(files))); return; }
    if (!text && !files.length) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const all = text + "\n" + (await filesText(files));
    if (await allowed("drop", all) && text) insert(e.target, text);
    // A dropped file is not re-dropped: the person can attach it again through the file picker.
  }, true);

  document.addEventListener("change", async (e) => {
    const input = e.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file" || !input.files?.length) return;
    if (input.dataset.saviochecked === "1") { delete input.dataset.saviochecked; return; }
    const text = await filesText([...input.files]);
    if (!text) return;
    if (mode === "log") { check("file", text); return; }
    e.stopImmediatePropagation();
    if (await allowed("file", text)) {
      input.dataset.saviochecked = "1";
      input.dispatchEvent(new Event("change", { bubbles: true }));   // let the site see it now
    } else {
      input.value = "";
    }
  }, true);

  document.addEventListener("submit", async (e) => {
    if (resubmitting) return;
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    const text = [...form.querySelectorAll("textarea, input:not([type=password]):not([type=hidden])")]
      .map((el) => el.value).filter(Boolean).join("\n");
    if (text.length < 8) return;
    if (mode === "log") { check("submit", text); return; }
    e.preventDefault();
    e.stopImmediatePropagation();
    if (await allowed("submit", text)) {
      resubmitting = true;
      try { form.requestSubmit(); } finally { resubmitting = false; }
    }
  }, true);
})();
