import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // In production the console is served from /static/console/ by Django/Whitenoise.
  base: mode === "production" ? "/static/console/" : "/",
  css: {
    postcss: "./postcss.config.js",
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
}))
