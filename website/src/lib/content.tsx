"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

/**
 * Runtime content layer.
 *
 * Every visible string has its ORIGINAL text as a built-in fallback, so the
 * site renders identically even if /content.json is missing or a key is absent.
 * At runtime we fetch /content.json and let it OVERRIDE those defaults — so the
 * text can be edited directly on the server (Hostinger File Manager) with no
 * rebuild. Because SSG renders the fallbacks, SEO/first paint are unaffected.
 */

type Dict = { [key: string]: unknown };

const ContentContext = createContext<Dict>({});

export function ContentProvider({ children }: { children: React.ReactNode }) {
  const [content, setContent] = useState<Dict>({});

  useEffect(() => {
    fetch("/content.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && typeof data === "object") setContent(data as Dict);
      })
      .catch(() => {
        /* keep fallbacks */
      });
  }, []);

  return (
    <ContentContext.Provider value={content}>
      {children}
    </ContentContext.Provider>
  );
}

function getPath(obj: Dict, path: string): unknown {
  return path
    .split(".")
    .reduce<unknown>(
      (o, k) =>
        o != null && typeof o === "object"
          ? (o as Dict)[k]
          : undefined,
      obj,
    );
}

export function useContent() {
  const content = useContext(ContentContext);

  /** Get a string by dotted path, falling back to the original text. */
  const c = (path: string, fallback = ""): string => {
    const v = getPath(content, path);
    return typeof v === "string" ? v : fallback;
  };

  /** Get an array by dotted path, falling back to the original array. */
  function list<T>(path: string, fallback: T[]): T[] {
    const v = getPath(content, path);
    return Array.isArray(v) ? (v as T[]) : fallback;
  }

  return { c, list };
}

/**
 * Renders editable text with light markup:
 *   [[text]]  → brand gradient highlight
 *   **text**  → bold
 *   \n        → line break
 */
export function Rich({ text }: { text: string }) {
  const out: React.ReactNode[] = [];
  const lines = text.split("\n");
  lines.forEach((line, li) => {
    if (li > 0) out.push(<br key={`br-${li}`} />);
    const parts = line.split(/(\[\[[^\]]+\]\]|\*\*[^*]+\*\*)/g);
    parts.forEach((p, pi) => {
      if (!p) return;
      const key = `${li}-${pi}`;
      if (p.startsWith("[[") && p.endsWith("]]")) {
        out.push(
          <span key={key} className="gradient-text">
            {p.slice(2, -2)}
          </span>,
        );
      } else if (p.startsWith("**") && p.endsWith("**")) {
        out.push(<strong key={key}>{p.slice(2, -2)}</strong>);
      } else {
        out.push(<React.Fragment key={key}>{p}</React.Fragment>);
      }
    });
  });
  return <>{out}</>;
}
