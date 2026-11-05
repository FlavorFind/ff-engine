/// <reference types="vite/client" />

// API base URL and key are injected at runtime by the Django template
// via window.__FF_API_BASE__ and window.__FF_API_KEY__, not build-time
// env vars. See console/src/api.ts and templates/console/index.html.

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
