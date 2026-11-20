// Phase 3 · D7: SAVIO's own in-page prompts, in place of the browser's confirm() / alert().
//
// Loaded before content.js, in the extension's isolated world. The prompt lives in a CLOSED
// shadow root, so the page's scripts and styles cannot read, restyle or click it, and only
// trusted (real) clicks and keys count. If a page removes it, nothing is pasted or sent: the
// held action simply never happens.
//
// English only for now; every string is in TEXT, so another language is one table.
(() => {
  const TEXT = {
    verb: { paste: "paste", drop: "drop", file: "upload", submit: "send" },
    title: { warn: "Check before you {verb}", justify: "Tell us why before you {verb}", block: "SAVIO blocked this",
             approve: "This needs approval from IT" },
    approveHelp: "Ask IT, and once they approve you can {verb} on this site for a while. Try again then.",
    ask: "Ask IT for approval",
    asked: "Request sent to IT.",
    askedHelp: "Once they approve, try again. You'll be able to {verb} on this site for a while.",
    unknown: "SAVIO could not check this content just now.",
    blocked: "Your organization does not allow this kind of data on this site.",
    stop: "Don't {verb}",
    go: "{Verb} anyway",
    ok: "OK",
    pick: "Why does this need to go here?",
    hidden: { paste: "Pasted with the sensitive parts hidden.", file: "Uploaded with the sensitive parts hidden.",
              submit: "Sent with the sensitive parts hidden." },
    footer: "Checked on this PC. Your organization sees what kind of data was found and where, never the text itself.",
  };
  const fill = (s, verb) => s.replace("{verb}", verb).replace("{Verb}", verb[0].toUpperCase() + verb.slice(1));

  const CSS = `
    :host { all: initial !important; }
    dialog.box { border: 0; margin: auto; font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
    dialog.box::backdrop { background: rgba(15,23,42,.45); }
    .box { --bg:#fff; --fg:#0f172a; --mut:#475569; --line:#e2e8f0; --accent:#2563eb; --on-accent:#fff; --warn:#b45309; --bad:#dc2626;
           background: var(--bg); color: var(--fg); border-radius: 12px; max-width: 440px; width: 100%;
           max-height: calc(100vh - 32px); overflow: auto; box-sizing: border-box;
           box-shadow: 0 20px 50px rgba(0,0,0,.3); padding: 20px; }
    @media (prefers-color-scheme: dark) {
      .box { --bg:#0f172a; --fg:#f1f5f9; --mut:#94a3b8; --line:#1e293b; --accent:#60a5fa; --on-accent:#0f172a; --warn:#fbbf24; --bad:#f87171; }
    }
    .brand { font-size: 12px; font-weight: 600; color: var(--accent); letter-spacing: .02em; }
    h2 { margin: 6px 0 8px; font-size: 17px; }
    .warn h2 { color: var(--warn); } .block h2 { color: var(--bad); }
    p { margin: 0 0 10px; color: var(--fg); }
    .mut { color: var(--mut); font-size: 12px; }
    fieldset { border: 1px solid var(--line); border-radius: 8px; margin: 0 0 12px; padding: 8px 10px; }
    legend { font-size: 12px; color: var(--mut); padding: 0 4px; }
    label { display: flex; gap: 8px; align-items: center; padding: 3px 0; cursor: pointer; }
    .row { display: flex; gap: 8px; justify-content: flex-end; margin-top: 14px; flex-wrap: wrap; }
    button { font: inherit; border-radius: 8px; padding: 7px 14px; cursor: pointer; border: 1px solid var(--line);
             background: transparent; color: var(--fg); }
    button.primary { background: var(--accent); border-color: var(--accent); color: var(--on-accent); }
    button:disabled { opacity: .45; cursor: not-allowed; }
    button:focus-visible, input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  `;

  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    for (const c of children) e.append(c);
    return e;
  }

  /**
   * Show one prompt. `result` is the background's answer: action (warn | justify | block),
   * reason (what was found, as words), unknown, and for justify the list of reasons.
   * Resolves { outcome: "proceeded" | "cancelled", reason } (block always "cancelled").
   */
  function show(kind, result) {
    return new Promise((resolve) => {
      const verb = TEXT.verb[kind] ?? "continue";
      const action = result.action;
      const host = el("savio-guard-dialog");
      const root = host.attachShadow({ mode: "closed" });
      // A modal <dialog> sits in the browser's top layer, above anything the page draws, whatever
      // its z-index; `all: initial !important` keeps page CSS off the host (security review L1).
      const box = el("dialog", { class: `box ${action}`, role: "alertdialog", "aria-labelledby": "t" });
      root.append(el("style", {}, CSS), box);

      box.append(el("div", { class: "brand" }, "SAVIO Guard"),
                 el("h2", { id: "t" }, fill(TEXT.title[action] ?? TEXT.title.warn, verb)),
                 el("p", {}, result.unknown ? TEXT.unknown : (result.reason ?? "")));
      if (action === "block") box.append(el("p", { class: "mut" }, TEXT.blocked));
      if (action === "approve") box.append(el("p", { class: "mut" }, fill(TEXT.approveHelp, verb)));

      let chosen = null;
      const go = el("button", {}, fill(TEXT.go, verb));
      if (action === "justify") {
        const set = el("fieldset", {}, el("legend", {}, TEXT.pick));
        for (const [code, label] of Object.entries(result.reasons ?? {})) {
          const radio = el("input", { type: "radio", name: "why", value: code });
          radio.addEventListener("change", (e) => { if (e.isTrusted) { chosen = code; go.disabled = false; } });
          set.append(el("label", {}, radio, label));
        }
        box.append(set);
        go.disabled = true;
      }

      let settled = false;
      let watcher = null;
      const done = (outcome) => {
        if (settled) return;
        settled = true;
        watcher?.disconnect();
        host.remove();
        resolve({ outcome, reason: outcome === "proceeded" ? chosen : null });
      };
      // A click in the first moments after it opens is not taken: a page cannot time a
      // click-through onto "anyway" as the prompt appears.
      const opened = performance.now();
      const real = (e) => e.isTrusted && performance.now() - opened > 400;
      const row = el("div", { class: "row" });
      let first;
      if (action === "block") {
        first = el("button", { class: "primary" }, TEXT.ok);
        first.addEventListener("click", (e) => e.isTrusted && done("cancelled"));
        row.append(first);
      } else if (action === "approve") {
        first = el("button", { class: "primary" }, fill(TEXT.stop, verb));
        const ask = el("button", {}, TEXT.ask);
        first.addEventListener("click", (e) => e.isTrusted && done("cancelled"));
        ask.addEventListener("click", (e) => real(e) && done("requested"));
        row.append(ask, first);
      } else {
        first = el("button", { class: "primary" }, fill(TEXT.stop, verb));
        first.addEventListener("click", (e) => e.isTrusted && done("cancelled"));
        go.addEventListener("click", (e) => real(e) && !go.disabled && done("proceeded"));
        row.append(go, first);
      }
      box.append(row, el("p", { class: "mut" }, TEXT.footer));
      // Escape on a modal dialog fires "cancel".
      box.addEventListener("cancel", (e) => { e.preventDefault(); if (e.isTrusted) done("cancelled"); });

      (document.body ?? document.documentElement).append(host);
      box.showModal();
      first.focus();   // the safe choice has the focus, so Enter never sends by accident
      // If the page removes the prompt, the answer is "no": the held action never happens.
      watcher = new MutationObserver(() => { if (!host.isConnected) done("cancelled"); });
      watcher.observe(document.documentElement, { childList: true, subtree: true });
    });
  }

  /** A short note that does not stop the person, gone after a few seconds: after a redacted
   *  paste, form or upload ("hidden"), or after asking IT for approval ("asked"). */
  function notice(kind, detail, channel = "paste") {
    const verb = TEXT.verb[channel] ?? "continue";
    const [title, more] = kind === "asked" ? [TEXT.asked, fill(TEXT.askedHelp, verb)]
      : [TEXT.hidden[channel] ?? TEXT.hidden.paste, detail ?? ""];
    document.querySelectorAll("savio-guard-notice").forEach((n) => n.remove());   // one at a time
    const host = el("savio-guard-notice");
    const root = host.attachShadow({ mode: "closed" });
    const box = el("div", { class: "box toast", role: "status" },
      el("div", { class: "brand" }, "SAVIO Guard"),
      el("p", {}, title), el("p", { class: "mut" }, more));
    root.append(el("style", {}, CSS + `
      .toast { position: fixed; right: 16px; bottom: 16px; z-index: 2147483647; max-width: 360px; width: auto;
               font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; padding: 14px 16px; }
      .toast { display: block; }
      .toast p { margin: 4px 0 0; }`), box);
    (document.body ?? document.documentElement).append(host);
    setTimeout(() => host.remove(), 6000);
  }

  globalThis.__savioGuardDialog = show;
  globalThis.__savioGuardNotice = notice;
})();
