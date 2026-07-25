"use client";

import { motion } from "framer-motion";

/** Ambient animated gradient blobs + grid, used behind hero sections. */
export function AnimatedBackground({ dense = false }: { dense?: boolean }) {
  return (
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 grid-bg opacity-70" />
      <motion.div
        className="absolute -left-32 -top-24 h-[420px] w-[420px] rounded-full bg-brand-500/25 blur-[120px]"
        animate={{ x: [0, 40, 0], y: [0, 30, 0], scale: [1, 1.1, 1] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -right-24 top-10 h-[380px] w-[380px] rounded-full bg-violet-500/25 blur-[120px]"
        animate={{ x: [0, -30, 0], y: [0, 40, 0], scale: [1, 1.15, 1] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      {dense && (
        <motion.div
          className="absolute bottom-0 left-1/3 h-[360px] w-[360px] rounded-full bg-sky-400/20 blur-[120px]"
          animate={{ x: [0, 30, 0], y: [0, -20, 0] }}
          transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <div
        className="absolute inset-x-0 bottom-0 h-40"
        style={{ background: "linear-gradient(to bottom, transparent, var(--bg))" }}
      />
    </div>
  );
}
