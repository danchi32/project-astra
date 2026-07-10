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
        brand: {
          50: "#eff6ff",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          900: "#1e3a8a",
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
