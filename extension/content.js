// Phase 3 · D3: watches the four ways text leaves a page: paste, drop, file upload and form
// submit.
//
// In "log" mode nothing is held up: the content is checked afterwards and only the counts are
// recorded. In the other modes the action is held, checked by the local scanner (a few
// milliseconds), then carried out, confirmed or refused in SAVIO's own prompt (dialog.js).
//
// Hardened after the phase-3 security review:
// - listeners sit on `window` in the capture phase, registered at document_start before any
//   page script, so a page cannot see a paste before SAVIO does (M1);
// - only real (trusted) events count, so a page cannot fake findings or flood prompts (M6);
// - a file choice is stopped synchronously, before any await, so the site's own handler never
//   sees the files while they are being checked (H1);
// - pasted files are checked like dropped ones (M2), and files that cannot be read are
//   "could not check", never silently clean (M3).
// Known limits of an in-page check: text typed and sent by a page's own script (fetch / XHR /
// WebSocket), `form.submit()`, and reads of the clipboard API are not seen. See docs.
(() => {
  const MAX_FILE_BYTES = 5 * 1024 * 1024;
  const TEXT_FILE = /\.(txt|csv|tsv|json|md|xml|log|html?)$/i;
  // Files that hold text SAVIO cannot read here. A photo or a video is not one of them.
  const DOCUMENT = /\.(pdf|docx?|xlsx?|xlsm|pptx?|odt|ods|odp|rtf|zip|rar|7z)$/i;
  const MIN_TEXT = 4;
  const MODES = ["log", "warn", "justify", "redact", "approve", "block"];
  let mode = "log";
  let resubmitting = false;
  const checkedInputs = new WeakSet();   // not a DOM attribute, which the page could set (L2)

  const readMode = (m) => { if (m && MODES.includes(m.mode)) mode = m.mode; };
  chrome.storage.managed.get("mode").then(readMode).catch(() => {});
  // A tighter policy reaches open tabs at once, not after a reload (L3).
  chrome.storage.onChanged?.addListener((changes, area) => {
    if (area === "managed" && changes.mode) readMode({ mode: changes.mode.newValue });
  });

  const check = (kind, text, unreadable = 0) =>
    chrome.runtime.sendMessage({ type: "check", kind, text, unreadable })
      .catch(() => ({ action: "warn", unknown: true }));

  // The text to go ahead with (the original, or with the sensitive parts hidden), or null.
  async function handled(kind, text, unreadable = 0) {
    const r = await check(kind, text, unreadable);
    if (r.action === "allow") return text;
    if (r.action === "redact" && typeof r.redacted === "string") {
      globalThis.__savioGuardNotice("hidden", r.reason);
      return r.redacted;
    }
    const answer = await globalThis.__savioGuardDialog(kind, r);
    if (r.pending) {
      // Only the id goes back: the background holds the event itself (M5).
      chrome.runtime.sendMessage({ type: "outcome", id: r.pending, outcome: answer.outcome, reason: answer.reason })
        .catch(() => {});
    }
    if (answer.outcome === "requested") globalThis.__savioGuardNotice("asked", null, kind);
    return ["warn", "justify"].includes(r.action) && answer.outcome === "proceeded" ? text : null;
  }
  const allowed = async (kind, text, unreadable = 0) => (await handled(kind, text, unreadable)) !== null;

  function insert(target, text) {
    target?.focus?.();
    document.execCommand("insertText", false, text);
  }

  /** The text of the files we can read, and how many documents we could not (an Office file,
   *  a PDF, an archive, or a text file too big): those make the check "could not check". */
  async function filesText(files) {
    const parts = [];
    let unreadable = 0;
    for (const f of files) {
      const textual = f.type.startsWith("text/") || TEXT_FILE.test(f.name);
      if (textual && f.size <= MAX_FILE_BYTES) {
        try { parts.push(await f.text()); } catch { unreadable++; }
      } else if (textual || DOCUMENT.test(f.name)) {
        unreadable++;
      }
    }
    return { text: parts.join("\n"), unreadable };
  }

  window.addEventListener("paste", (e) => {
    if (!e.isTrusted) return;
    const files = [...(e.clipboardData?.files ?? [])];
    const text = e.clipboardData?.getData("text/plain") ?? "";
    if (text.length < MIN_TEXT && !files.length) return;
    if (mode === "log") {
      filesText(files).then((f) => check("paste", [text, f.text].join("\n"), f.unreadable));
      return;
    }
    e.preventDefault();
    e.stopImmediatePropagation();
    const target = e.target;
    filesText(files).then(async (f) => {
      if (!files.length) {
        const out = await handled("paste", text);
        if (out !== null) insert(target, out);
        return;
      }
      // Pasted files cannot be re-pasted after a check: the person pastes again if allowed.
      await allowed("paste", [text, f.text].join("\n"), f.unreadable);
    });
  }, true);

  window.addEventListener("drop", async (e) => {
    if (!e.isTrusted) return;
    const dt = e.dataTransfer;
    if (!dt) return;
    const files = [...(dt.files ?? [])];
    const text = dt.getData("text/plain") || "";
    if (!text && !files.length) return;
    if (mode !== "log") {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
    const f = await filesText(files);
    if (mode === "log") { check("drop", [text, f.text].join("\n"), f.unreadable); return; }
    if (await allowed("drop", [text, f.text].join("\n"), f.unreadable) && text) insert(e.target, text);
    // A dropped file is not re-dropped: the person can attach it again through the file picker.
  }, true);

  // A file choice fires `input` then `change`; both are held while the files are checked.
  const onFiles = async (e) => {
    const input = e.target;
    if (!e.isTrusted || !(input instanceof HTMLInputElement) || input.type !== "file" || !input.files?.length) return;
    if (checkedInputs.has(input)) { if (e.type === "change") checkedInputs.delete(input); return; }
    // Stopped now, synchronously: after an await the site would already have the files (H1).
    if (mode !== "log") e.stopImmediatePropagation();
    if (e.type === "input") return;   // the check runs once, on change
    const f = await filesText([...input.files]);
    if (mode === "log") { if (f.text || f.unreadable) check("file", f.text, f.unreadable); return; }
    if (await allowed("file", f.text, f.unreadable)) {
      checkedInputs.add(input);
      input.dispatchEvent(new Event("input", { bubbles: true }));    // let the site see it now
      input.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      input.value = "";
    }
  };
  window.addEventListener("input", onFiles, true);
  window.addEventListener("change", onFiles, true);

  window.addEventListener("submit", async (e) => {
    if (resubmitting || !e.isTrusted) return;
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    // Every field the form will send, including ones placed outside it with form="…" (L4).
    let text = "";
    try {
      const data = new FormData(form, e.submitter ?? undefined);
      text = [...data.entries()]
        .filter(([name, v]) => typeof v === "string" && !/pass(word)?|pwd/i.test(name))
        .map(([, v]) => v).filter(Boolean).join("\n");
    } catch { return; }
    if (text.length < MIN_TEXT) return;
    if (mode === "log") { check("submit", text); return; }
    e.preventDefault();
    e.stopImmediatePropagation();
    const submitter = e.submitter;
    if (await allowed("submit", text)) {
      resubmitting = true;
      try { form.requestSubmit(submitter && submitter.form === form ? submitter : undefined); } finally { resubmitting = false; }
    }
  }, true);
})();
