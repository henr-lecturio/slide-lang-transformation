import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  root: "web",
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        "main-app": "web/src/main-app.js",
        "lab-app": "web/src/main.js",
        "health-app": "web/src/health-main.js",
      },
      output: {
        entryFileNames: "[name].js",
        assetFileNames: "[name][extname]",
      },
    },
  },
});
