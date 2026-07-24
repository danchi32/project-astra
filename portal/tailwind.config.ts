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
        // Technomate purple (from the logo mark).
        brand: {
          50: "#fbf3fe",
          100: "#f5e2fc",
          200: "#ecc6f9",
          300: "#dd9cf2",
          400: "#c86ce7",
          500: "#b246d4",
          600: "#9a2fbb",
          700: "#7f2599",
          800: "#69217b",
          900: "#561d64",
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
