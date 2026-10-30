"use client";

import { motion } from "framer-motion";

/**
 * Shared bits for the website templates in this folder.
 *
 * Every template takes `compact` (lay out for a phone: the 390px preview
 * frame, or a real phone) and `thumb` (drawn scaled down inside a gallery
 * card: skip anything heavy, like WebGL). Templates switch layout on
 * `compact`, never on Tailwind breakpoints — breakpoints read the browser's
 * width, which says nothing about a phone frame or a thumbnail.
 */
export type TplProps = { compact?: boolean; thumb?: boolean };

// One stylesheet for every template font. React 19 hoists it into <head> and
// de-duplicates it, so each template can render <TplFonts /> freely, and the
// fonts load only on pages that show a template.
const FONTS =
  "https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Fredoka:wght@400;500;600;700&family=Manrope:wght@400;500;700;800&family=Nunito:wght@400;600;700;800&family=Outfit:wght@300;400;600;800&family=Playfair+Display:ital,wght@0,500;0,700;1,500&family=Plus+Jakarta+Sans:wght@400;500;700;800&family=Space+Grotesk:wght@400;500;700&family=Syne:wght@500;700;800&display=swap";

export function TplFonts() {
  return <link rel="stylesheet" href={FONTS} precedence="default" />;
}

export const font = {
  manrope: "'Manrope', system-ui, sans-serif",
  outfit: "'Outfit', system-ui, sans-serif",
  grotesk: "'Space Grotesk', system-ui, sans-serif",
  jakarta: "'Plus Jakarta Sans', system-ui, sans-serif",
  syne: "'Syne', system-ui, sans-serif",
  playfair: "'Playfair Display', Georgia, serif",
  dmserif: "'DM Serif Display', Georgia, serif",
  nunito: "'Nunito', system-ui, sans-serif",
  fredoka: "'Fredoka', system-ui, sans-serif",
};

/** Fade/slide in once when scrolled into view. */
export function In({
  children,
  delay = 0,
  y = 28,
  x = 0,
  className,
  style,
}: {
  children: React.ReactNode;
  delay?: number;
  y?: number;
  x?: number;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y, x }}
      whileInView={{ opacity: 1, y: 0, x: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.7, delay, ease: [0.21, 0.47, 0.32, 0.98] }}
      className={className}
      style={style}
    >
      {children}
    </motion.div>
  );
}

/** Seamless horizontal loop of its children. */
export function Loop({
  children,
  duration = 20,
  reverse = false,
  className,
}: {
  children: React.ReactNode;
  duration?: number;
  reverse?: boolean;
  className?: string;
}) {
  return (
    <div className={`overflow-hidden ${className ?? ""}`}>
      <motion.div
        className="flex w-max"
        animate={{ x: reverse ? ["-50%", "0%"] : ["0%", "-50%"] }}
        transition={{ duration, ease: "linear", repeat: Infinity }}
      >
        {children}
        {children}
      </motion.div>
    </div>
  );
}

/** Columns that collapse to one in compact mode. */
export const cols = (compact: boolean | undefined, n: number) =>
  compact ? "grid-cols-1" : ({ 2: "grid-cols-2", 3: "grid-cols-3", 4: "grid-cols-4" } as Record<number, string>)[n];
