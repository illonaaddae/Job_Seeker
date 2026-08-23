import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5273,
    // The Python API serves the same routes in production, so proxying in dev
    // keeps fetch paths identical in both environments.
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8787",
        changeOrigin: true,
      },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
