# Beli Buzz Frontend

React + Vite single-page app that reads `latest.json` from S3 (or `public/data.json` locally) and renders Toronto's trending restaurants on top of Google Maps via `@vis.gl/react-google-maps`.

## Available scripts

- `pnpm dev` – local development at <http://localhost:5173>.
- `pnpm build` – production build (used by Cloudflare Pages).
- `pnpm preview` – run the built bundle locally.

## Environment variables

Create `frontend/.env` with:

```
VITE_GOOGLE_MAPS_API_KEY=your_browser_maps_key
VITE_TRENDING_DATA_URL=/data.json # or S3 URL in production
```

## Data flow

1. Run the backend job (`python backend/main_job.py --mock-data`) which rewrites `public/data.json`.
2. Start the dev server; the app auto-refreshes when the JSON changes.
3. For production, point `VITE_TRENDING_DATA_URL` at the publicly readable S3 object populated by Lambda.

See the repository-level `README.md` for the full architecture and deployment checklist.
