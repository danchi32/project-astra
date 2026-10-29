import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";
import { join } from "path";

// Resolved from this file's directory (jiti provides __dirname) rather than
// process.cwd(): launched from the monorepo root, a "./src/**" glob matches nothing and
// Tailwind emits no utilities at all, so the dev site renders as unstyled HTML while the
// production build — run from this directory — looks fine. Forward slashes are required
// by fast-glob. Same fix as portal/tailwind.config.ts.
const srcGlob = join(__dirname, "src/**/*.{js,ts,jsx,tsx,mdx}").replace(/\\/g, "/");

const config: Config = {
  darkMode: "class",
  content: [srcGlob],
  theme: {
    extend: {
      colors: {
        // Brand palette — SAVIO blue, the same ramp as the portal (portal/tailwind.config.ts).
        // The Technomate logo keeps its own colours; it is an image, not this palette.
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
        // Deep navy from the wordmark — used for text / dark surfaces.
        ink: {
          700: "#1e293b",
          800: "#131c2e",
          900: "#0b1120",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.6s ease-out both",
        float: "float 6s ease-in-out infinite",
        shimmer: "shimmer 3s linear infinite",
      },
    },
  },
  plugins: [typography],
};

export default config;
