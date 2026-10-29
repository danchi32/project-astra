import type { Config } from "tailwindcss";
import { join } from "path";

// Resolve content from this file's directory (jiti provides __dirname), not
// process.cwd(), so utilities are generated even when the dev server is
// launched from the monorepo root. Forward slashes are required by fast-glob.
const srcGlob = join(__dirname, "src/**/*.{ts,tsx}").replace(/\\/g, "/");

const config: Config = {
  darkMode: "class",
  content: [srcGlob],
  theme: {
    extend: {
      colors: {
        // SAVIO blue (from the logo mark, docs/brand/savio-icon.svg).
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
        // The cyan the agent's eyes and signal glow in — the "AI" accent, used sparingly.
        glow: {
          300: "#67e8f9",
          400: "#22d3ee",
          500: "#06b6d4",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
