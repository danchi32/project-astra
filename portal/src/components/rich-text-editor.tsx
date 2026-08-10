"use client";
import { useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react";
import {
  Bold, Italic, Underline, List, ListOrdered, Link2, RemoveFormatting, Code,
} from "lucide-react";

export interface RichTextHandle {
  /** Drop text in at the caret — used by the placeholder picker, which lives outside the
   *  editor and therefore takes focus away from it before it can act. */
  insertText: (text: string) => void;
}

/** A small rich-text editor: a contentEditable body plus the formatting an email template
 *  actually needs.
 *
 *  Built on document.execCommand, which is deprecated and has no replacement that does not
 *  mean shipping a whole editor framework. For bold/italic/lists inside one text field, the
 *  deprecated API is supported everywhere and costs nothing; a dependency for this would be
 *  larger than the feature.
 *
 *  What the toolbar can produce is not the security boundary. The server reduces the markup
 *  to its own allowlist on save and again on send, so anything added here that the allowlist
 *  does not know is dropped rather than delivered.
 */
export const RichTextEditor = forwardRef<RichTextHandle, {
  value: string;
  onChange: (html: string) => void;
  minHeight?: number;
}>(function RichTextEditor({ value, onChange, minHeight = 180 }, ref) {
  const boxRef = useRef<HTMLDivElement>(null);
  const savedRange = useRef<Range | null>(null);
  const [source, setSource] = useState(false);

  // Write into the DOM only when the incoming value is not what is already there. Assigning
  // innerHTML on every render would move the caret to the start on each keystroke.
  useEffect(() => {
    const el = boxRef.current;
    if (el && !source && el.innerHTML !== value) el.innerHTML = value;
  }, [value, source]);

  /** Remember where the caret was. Clicking any button outside the editor — a toolbar icon
   *  or a placeholder chip — clears the selection before the handler runs. */
  const remember = () => {
    const sel = window.getSelection();
    if (sel && sel.rangeCount && boxRef.current?.contains(sel.anchorNode)) {
      savedRange.current = sel.getRangeAt(0).cloneRange();
    }
  };

  const restore = () => {
    const el = boxRef.current;
    if (!el) return;
    el.focus();
    const sel = window.getSelection();
    if (!sel) return;
    if (savedRange.current && el.contains(savedRange.current.commonAncestorContainer)) {
      sel.removeAllRanges();
      sel.addRange(savedRange.current);
    } else {
      // No usable caret — append rather than silently doing nothing where the user clicked.
      const end = document.createRange();
      end.selectNodeContents(el);
      end.collapse(false);
      sel.removeAllRanges();
      sel.addRange(end);
    }
  };

  const emit = () => {
    const el = boxRef.current;
    if (el) onChange(el.innerHTML);
  };

  const exec = (command: string, arg?: string) => {
    restore();
    document.execCommand(command, false, arg);
    remember();
    emit();
  };

  useImperativeHandle(ref, () => ({
    insertText: (text: string) => {
      if (source) { onChange(value + text); return; }
      restore();
      document.execCommand("insertText", false, text);
      remember();
      emit();
    },
  }), [source, value, onChange]);

  function addLink() {
    restore();
    const url = window.prompt("Link address", "https://");
    // Only the schemes the server will keep. Offering a link the send path silently strips
    // is worse than refusing it here, where the author can still do something about it.
    if (!url || !/^(https?:|mailto:)/i.test(url)) return;
    exec("createLink", url);
  }

  const btn = "p-1.5 rounded-md";
  const btnStyle = { color: "var(--text-secondary)" };

  return (
    <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
      <div className="flex items-center gap-0.5 px-1.5 py-1 flex-wrap"
        style={{ borderBottom: "1px solid var(--border)", background: "var(--bg)" }}>
        <button type="button" title="Bold" className={btn} style={btnStyle}
          onMouseDown={(e) => e.preventDefault()} onClick={() => exec("bold")}><Bold size={14} /></button>
        <button type="button" title="Italic" className={btn} style={btnStyle}
          onMouseDown={(e) => e.preventDefault()} onClick={() => exec("italic")}><Italic size={14} /></button>
        <button type="button" title="Underline" className={btn} style={btnStyle}
          onMouseDown={(e) => e.preventDefault()} onClick={() => exec("underline")}><Underline size={14} /></button>
        <span className="w-px h-4 mx-1" style={{ background: "var(--border)" }} />
        <button type="button" title="Bulleted list" className={btn} style={btnStyle}
          onMouseDown={(e) => e.preventDefault()} onClick={() => exec("insertUnorderedList")}><List size={14} /></button>
        <button type="button" title="Numbered list" className={btn} style={btnStyle}
          onMouseDown={(e) => e.preventDefault()} onClick={() => exec("insertOrderedList")}><ListOrdered size={14} /></button>
        <span className="w-px h-4 mx-1" style={{ background: "var(--border)" }} />
        <button type="button" title="Link" className={btn} style={btnStyle}
          onMouseDown={(e) => e.preventDefault()} onClick={addLink}><Link2 size={14} /></button>
        <button type="button" title="Clear formatting" className={btn} style={btnStyle}
          onMouseDown={(e) => e.preventDefault()} onClick={() => exec("removeFormat")}><RemoveFormatting size={14} /></button>
        <button type="button" title={source ? "Back to editor" : "Edit HTML"}
          className={`${btn} ml-auto`} style={{ color: source ? "var(--accent)" : "var(--text-secondary)" }}
          onMouseDown={(e) => e.preventDefault()} onClick={() => setSource((v) => !v)}><Code size={14} /></button>
      </div>

      {source ? (
        <textarea value={value} onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-2 text-sm outline-none font-mono resize-y"
          style={{ background: "var(--bg)", color: "var(--text-primary)", minHeight }} />
      ) : (
        <div ref={boxRef} contentEditable suppressContentEditableWarning
          onInput={emit} onBlur={() => { remember(); emit(); }}
          onKeyUp={remember} onMouseUp={remember}
          className="astra-rte px-3 py-2 text-sm outline-none overflow-y-auto"
          style={{ background: "var(--bg)", color: "var(--text-primary)", minHeight, maxHeight: 420 }} />
      )}
    </div>
  );
});
