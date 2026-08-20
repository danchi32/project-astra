import { fileURLToPath } from "url";
import { dirname, join } from "path";

// Resolve the Tailwind config by this file's own location, not process.cwd().
// Next.js may be launched from the monorepo root, in which case Tailwind's
// default CWD-based config discovery would silently fail and emit no utilities —
// the dev site then renders as unstyled HTML while `npm run build`, run from this
// directory, looks perfectly fine. Same fix as portal/postcss.config.mjs.
const here = dirname(fileURLToPath(import.meta.url));

/** @type {import('postcss-load-config').Config} */
const config = {
  plugins: {
    tailwindcss: { config: join(here, "tailwind.config.ts") },
    autoprefixer: {},
  },
};

export default config;
