# Flavor Find — Internal Test Console

A small React app for the team to test the engine API, inspect search results,
compare weight tuning, and spot data gaps.

Not a public product. CORS is closed on the engine except for this console's origin.

## Setup

```bash
cp .env.example .env.local
# Fill in VITE_API_BASE and VITE_API_KEY

npm install
npm run dev      # http://localhost:5173
```

## Build

```bash
npm run build    # type-check + production bundle to dist/
npm run preview  # serve the built bundle
```

## Features

- **Search** — enter ingredients, see tiered results (exact / can make / almost)
  with full score breakdowns and explanations.
- **Strict / Explore** — toggle search modes.
- **Weight editor** — adjust scoring weights live and compare two weight sets
  side-by-side on the same query.
- **Resolved tokens** — see how each ingredient input was resolved (matched,
  ambiguous, unmatched) with method and confidence.
- **Latency display** — response time shown per search, flagged red if > 300ms.
- **Dataset version** — header shows engine + dataset version from the API.

## Tech

React 19 · Vite · TypeScript · Tailwind CSS 3 · oxlint
