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
      input: "web/src/main.js",
      output: {
        entryFileNames: "lab-app.js",
        assetFileNames: "lab-app[extname]",
      },
    },
  },
});
