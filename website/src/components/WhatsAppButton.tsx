"use client";

import { usePathname } from "next/navigation";
import { site } from "@/lib/site";

/**
 * Floating WhatsApp click-to-chat, bottom-left on every page — the site assistant owns
 * bottom-right. Most Indian SMB buyers would rather message than fill a form, so this
 * is the shortest path from "interested" to a conversation.
 *
 * The message is prefilled with the page the visitor was on, so the first reply can
 * start from context. Clicks are counted by ConversionTracker (it matches wa.me links),
 * not here, so every WhatsApp link on the site is covered the same way.
 */
export function WhatsAppButton() {
  const pathname = usePathname();
  const text = `Hi ${site.brandShort}, I'd like to know more about your IT services. (via ${site.domain}${pathname})`;
  const href = `https://wa.me/${site.contact.whatsapp}?text=${encodeURIComponent(text)}`;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener"
      aria-label="Chat with us on WhatsApp"
      title="Chat with us on WhatsApp"
      className="group fixed bottom-5 left-5 z-50 flex h-14 items-center gap-0 rounded-full bg-[#25D366] px-[1.05rem] text-sm font-semibold text-white shadow-xl shadow-black/20 transition-all duration-300 hover:gap-2 hover:pl-5 hover:pr-6 focus-visible:gap-2 focus-visible:pl-5 focus-visible:pr-6"
    >
      {/* WhatsApp glyph — lucide has no brand icons. */}
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="h-6 w-6 shrink-0">
        <path d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.17-.17.2-.35.22-.65.07-.3-.15-1.26-.46-2.4-1.48-.89-.79-1.49-1.77-1.66-2.07-.17-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.62-.92-2.22-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.04 1.02-1.04 2.48 0 1.46 1.07 2.88 1.21 3.08.15.2 2.1 3.2 5.08 4.49.71.31 1.26.49 1.7.63.71.23 1.36.2 1.87.12.57-.09 1.76-.72 2.01-1.41.25-.7.25-1.29.17-1.41-.07-.13-.27-.2-.57-.35zM12.05 21.5h-.01a9.4 9.4 0 0 1-4.8-1.32l-.34-.2-3.57.94.95-3.48-.22-.36a9.43 9.43 0 0 1-1.45-5.03c0-5.2 4.24-9.44 9.45-9.44 2.52 0 4.89.99 6.67 2.77a9.37 9.37 0 0 1 2.76 6.68c0 5.21-4.24 9.44-9.44 9.44zm8.04-17.48A11.3 11.3 0 0 0 12.05.7C5.78.7.68 5.8.68 12.06c0 2 .52 3.96 1.52 5.68L.58 23.7l6.1-1.6a11.33 11.33 0 0 0 5.37 1.37h.01c6.26 0 11.36-5.1 11.37-11.36 0-3.04-1.18-5.89-3.34-8.04z" />
      </svg>
      <span className="max-w-0 overflow-hidden whitespace-nowrap opacity-0 transition-all duration-300 group-hover:max-w-[10rem] group-hover:opacity-100 group-focus-visible:max-w-[10rem] group-focus-visible:opacity-100">
        Chat on WhatsApp
      </span>
    </a>
  );
}
