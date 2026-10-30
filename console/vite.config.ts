import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react()],
  base: "/static/console/",
  css: {
    postcss: "./postcss.config.js",
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
})
