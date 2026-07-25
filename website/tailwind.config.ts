import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Brand palette — Technomate purple (from the logo mark).
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
  plugins: [],
};

export default config;
