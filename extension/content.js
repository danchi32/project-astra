// Phase 3 · D3: watches the four ways text leaves a page: paste, drop, file upload and form
// submit. Word and Excel files (and PDFs, where the org chose it) are read by the SAVIO host on
// this PC; in redact mode a paste, a form's text fields and text files go ahead with the
// sensitive parts hidden.
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
  const MAX_DOC_BYTES = 20 * 1024 * 1024;   // all documents in one check, sent to the host as base64
  const TEXT_FILE = /\.(txt|csv|tsv|json|md|xml|log|html?)$/i;
  // Read by the SAVIO host on this PC: Word and Excel always, PDF where the org chose it.
  const OFFICE = /\.(docx|xlsx)$/i;
  const PDF = /\.pdf$/i;
  // Files that hold text SAVIO cannot read. A photo or a video is not one of them.
  const DOCUMENT = /\.(pdf|docx?|xlsx?|xlsm|pptx?|odt|ods|odp|rtf|zip|rar|7z)$/i;
  const MIN_TEXT = 4;
  const MODES = ["log", "warn", "justify", "redact", "approve", "block"];
  let mode = "log";
  let readPdf = false;
  let resubmitting = false;

  const readMode = (m) => {
    if (m && MODES.includes(m.mode)) mode = m.mode;
    if (m && "readPdf" in m) readPdf = m.readPdf === true;
  };
  chrome.storage.managed.get(["mode", "readPdf"]).then(readMode).catch(() => {});
  // A tighter policy reaches open tabs at once, not after a reload (L3).
  chrome.storage.onChanged?.addListener((changes, area) => {
    if (area !== "managed") return;
    if (changes.mode) readMode({ mode: changes.mode.newValue });
    if (changes.readPdf) readMode({ readPdf: changes.readPdf.newValue });
  });

  // `what`: { text, unreadable, docs, parts }. `parts` are the pieces that can be rewritten
  // (form fields, text files); without them, all of `text` is one rewritable whole (a paste).
  const check = (kind, what) =>
    chrome.runtime.sendMessage({ type: "check", kind, ...what })
      .catch(() => ({ action: "warn", unknown: true }));

  // What to go ahead with ({ text, parts }: the originals, or with the sensitive parts hidden),
  // or null to stop.
  async function handled(kind, what) {
    const r = await check(kind, what);
    if (r.action === "allow") return what;
    if (r.action === "redact" && (typeof r.redacted === "string" || Array.isArray(r.redactedParts))) {
      globalThis.__savioGuardNotice("hidden", r.reason, kind);
      return { ...what, text: r.redacted ?? what.text, parts: r.redactedParts ?? what.parts };
    }
    const answer = await globalThis.__savioGuardDialog(kind, r);
    if (r.pending) {
      // Only the id goes back: the background holds the event itself (M5).
      chrome.runtime.sendMessage({ type: "outcome", id: r.pending, outcome: answer.outcome, reason: answer.reason })
        .catch(() => {});
    }
    if (answer.outcome === "requested") globalThis.__savioGuardNotice("asked", null, kind);
    return ["warn", "justify"].includes(r.action) && answer.outcome === "proceeded" ? what : null;
  }
  const allowed = async (kind, what) => (await handled(kind, what)) !== null;

  function insert(target, text) {
    target?.focus?.();
    document.execCommand("insertText", false, text);
  }

  // C2: name and size only, for the background to look up where a file was downloaded from.
  // They never go into an event.
  const meta = (files) => files.map((f) => ({ name: f.name, size: f.size }));

  function base64(buffer) {
    const bytes = new Uint8Array(buffer);
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }

  /** What can be checked in these files: the text of text files (each also a rewritable part,
   *  with its File), documents for the host, and how many could not be read (an old Office
   *  file, a PDF the org does not read, an archive, anything too big): "could not check". */
  async function filesText(files) {
    const parts = [], textFiles = [], docs = [];
    let unreadable = 0, docBytes = 0;
    for (const f of files) {
      const textual = f.type.startsWith("text/") || TEXT_FILE.test(f.name);
      const document = OFFICE.test(f.name) || (readPdf && PDF.test(f.name));
      if (textual && f.size <= MAX_FILE_BYTES) {
        try { parts.push(await f.text()); textFiles.push(f); } catch { unreadable++; }
      } else if (document && f.size <= MAX_FILE_BYTES && docBytes + f.size <= MAX_DOC_BYTES) {
        try { docs.push({ name: f.name, data: base64(await f.arrayBuffer()) }); docBytes += f.size; } catch { unreadable++; }
      } else if (textual || DOCUMENT.test(f.name)) {
        unreadable++;
      }
    }
    return { text: parts.join("\n"), parts, textFiles, docs, unreadable };
  }

  // The text fields a form will send, which can be rewritten: inputs of type text or search, and
  // text areas. Other fields (selects, hidden, e-mail, number…) are sent as they are.
  const PASSWORD = /pass(word)?|pwd/i;
  const editableFields = (form) => [...form.elements].filter((el) =>
    (el instanceof HTMLTextAreaElement || (el instanceof HTMLInputElement && ["text", "search"].includes(el.type))) &&
    el.name && !el.disabled && el.value && !PASSWORD.test(el.name));

  // A field's new value, set as the page's own framework expects (React and the like track it
  // through the native setter and an input event), so a script that sends the form sees it too.
  function setValue(el, value) {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const onPaste = (e) => {
    if (!e.isTrusted) return;
    const files = [...(e.clipboardData?.files ?? [])];
    const text = e.clipboardData?.getData("text/plain") ?? "";
    if (text.length < MIN_TEXT && !files.length) return;
    const withFiles = (f) => ({ text: [text, f.text].join("\n"), unreadable: f.unreadable, docs: f.docs, files: meta(files) });
    if (mode === "log") {
      filesText(files).then((f) => check("paste", withFiles(f)));
      return;
    }
    e.preventDefault();
    e.stopImmediatePropagation();
    const target = e.target;
    filesText(files).then(async (f) => {
      if (!files.length) {
        const out = await handled("paste", { text });
        if (out !== null) insert(target, out.text);
        return;
      }
      // Pasted files cannot be re-pasted after a check: the person pastes again if allowed.
      // Nothing here can be rewritten (parts: []), so redact asks instead.
      await allowed("paste", { ...withFiles(f), parts: [] });
    });
  };

  const onDrop = async (e) => {
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
    const what = { text: [text, f.text].join("\n"), unreadable: f.unreadable, docs: f.docs, files: meta(files) };
    if (mode === "log") { check("drop", what); return; }
    if (await allowed("drop", what) && text) insert(e.target, text);
    // A dropped file is not re-dropped: the person can attach it again through the file picker.
  };

  // A file choice fires `input` then `change`; both are held while the files are checked.
  const onFiles = async (e) => {
    const input = e.target;
    if (!e.isTrusted || !(input instanceof HTMLInputElement) || input.type !== "file" || !input.files?.length) return;
    // Stopped now, synchronously: after an await the site would already have the files (H1).
    if (mode !== "log") e.stopImmediatePropagation();
    if (e.type === "input") return;   // the check runs once, on change
    const chosen = [...input.files];
    const f = await filesText(chosen);
    if (mode === "log") {
      if (f.text || f.docs.length || f.unreadable) check("file", { text: f.text, unreadable: f.unreadable, docs: f.docs, files: meta(chosen) });
      return;
    }
    // In redact mode each text file is a part that can be rewritten; elsewhere it is plain text.
    const what = mode === "redact"
      ? { text: "", parts: f.parts, unreadable: f.unreadable, docs: f.docs, files: meta(chosen) }
      : { text: f.text, unreadable: f.unreadable, docs: f.docs, files: meta(chosen) };
    const out = await handled("file", what);
    // The person chose again while this was checked: that choice is checked on its own change
    // event, and this result does not apply to it (review M1).
    if (input.files.length !== chosen.length || [...input.files].some((x, i) => x !== chosen[i])) return;
    if (out !== null) {
      if (out.parts && out.parts !== what.parts) {
        // A copy of each text file with the sensitive parts hidden, same name and type, in place.
        const dt = new DataTransfer();
        for (const file of chosen) {
          const i = f.textFiles.indexOf(file);
          dt.items.add(i >= 0 && out.parts[i] !== f.parts[i]
            ? new File([out.parts[i]], file.name, { type: file.type, lastModified: file.lastModified }) : file);
        }
        input.files = dt.files;
      }
      // Re-sent events are untrusted, so this listener lets them through to the site; the next
      // real choice on this input is checked again (review H1: a "checked" mark let it skip).
      input.dispatchEvent(new Event("input", { bubbles: true }));    // let the site see it now
      input.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      input.value = "";
    }
  };
  // What a form will send: every field, including ones placed outside it with form="…" (L4).
  function formValues(form, submitter) {
    const data = new FormData(form, submitter ?? undefined);
    return [...data.entries()]
      .filter(([name, v]) => typeof v === "string" && !PASSWORD.test(name))
      .map(([, v]) => v).filter(Boolean);
  }
  const same = (a, b) => a.length === b.length && [...a].sort().join("\u0000") === [...b].sort().join("\u0000");

  const onSubmit = async (e) => {
    if (resubmitting || !e.isTrusted) return;
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    let values;
    try { values = formValues(form, e.submitter); } catch { return; }
    const text = values.join("\n");
    if (text.length < MIN_TEXT) return;
    if (mode === "log") { check("submit", { text }); return; }
    e.preventDefault();
    e.stopImmediatePropagation();
    await checkAndSend(form, e.submitter, values, 0);
  };

  async function checkAndSend(form, submitter, values, round) {
    // In redact mode the text fields are parts that can be rewritten; every other value the
    // form sends is the fixed rest (one occurrence of each field's value taken out of it).
    let fields = [];
    let what = { text: values.join("\n") };
    if (mode === "redact") {
      const rest = [...values];
      fields = editableFields(form).filter((el) => {
        const i = rest.indexOf(el.value);
        return i >= 0 && rest.splice(i, 1).length === 1;
      });
      what = { text: rest.join("\n"), parts: fields.map((el) => el.value) };
    }
    const out = await handled("submit", what);
    if (out === null) return;
    const before = fields.map((el) => el.value);
    fields.forEach((el, i) => { if (out.parts[i] !== el.value) setValue(el, out.parts[i]); });
    if (fields.length) await new Promise((r) => setTimeout(r, 0));   // let the page's framework catch up
    // Security review 3b M1: what goes now must be what was checked (with what SAVIO hid). A
    // field filled or changed while the check ran (a macro, a script) is checked again, twice at
    // most; past that the form is not sent, and the person can send it again.
    let now;
    try { now = formValues(form, submitter && submitter.form === form ? submitter : undefined); } catch { return; }
    const expected = [...values];
    before.forEach((v, i) => { const j = expected.indexOf(v); if (j >= 0) expected[j] = out.parts[i]; });
    if (!same(now, expected.filter(Boolean)) && now.join("\n").length >= MIN_TEXT) {
      if (round < 2) await checkAndSend(form, submitter, now, round + 1);
      return;
    }
    resubmitting = true;
    try { form.requestSubmit(submitter && submitter.form === form ? submitter : undefined); } finally { resubmitting = false; }
  }

  // Security review 3b (live test): a page that rewrites a frame with document.open() erases
  // every listener on it, SAVIO's too (the "Try it" panel of a code playground). So they are
  // attached by one function, again whenever the document is rewritten. Adding the same
  // listener twice does nothing, so attaching again is always safe.
  function attach() {
    window.addEventListener("paste", onPaste, true);
    window.addEventListener("drop", onDrop, true);
    window.addEventListener("input", onFiles, true);
    window.addEventListener("change", onFiles, true);
    window.addEventListener("submit", onSubmit, true);
  }
  attach();
  new MutationObserver(attach).observe(document, { childList: true });
})();
