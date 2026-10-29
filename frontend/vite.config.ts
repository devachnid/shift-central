import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

// Builds into static/dist with stable names: the Django templates reference
// main.js and main.css directly, and WhiteNoise's manifest storage adds the
// cache-busting hash at collectstatic. The output is committed (README).
export default defineConfig({
  plugins: [preact()],
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: "src/main.ts",
      output: { entryFileNames: "main.js", assetFileNames: "main[extname]" },
    },
  },
});
