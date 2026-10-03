# Tandem Web (PWA)

Responsive web client for the Tandem agent. On a phone, "Add to Home Screen"
installs it like a native app; on desktop it's a full chat + memory dashboard.

## Run

1. Start the Python API (from the repo root, with a model key in `.env`):
   ```
   uv run uvicorn tandem.server:app --reload
   ```
2. Start the web app:
   ```
   cd web
   cp .env.local.example .env.local
   npm install
   npm run dev
   ```
   Open http://localhost:3000.

## Notes
- `lib/api.ts` is the only file that knows the backend's shape.
- Add real `public/icon-192.png` and `icon-512.png` for full PWA installability.
