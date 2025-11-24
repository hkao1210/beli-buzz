# Beli Buzz MVP

Daily food-intel map for Toronto. A lightweight Python pipeline scrapes Reddit + curated critics once per day, analyzes the chatter with Gemini Flash, pushes a JSON snapshot to S3, and a Vite/React front-end renders the hotspots on Google Maps (hosted for free on Cloudflare Pages).

## Architecture

| Layer | Stack | Notes |
| --- | --- | --- |
| Scrapers | Python, PRAW, feedparser | Reddit hot posts (last 24h) + curated RSS (Dickison, Karon Liu, Toronto Life). |
| Intelligence | Gemini Flash 1.5 (fallback Hugging Face) | Prompt extracts restaurant name, sentiment, summary. Keyword heuristic for fully offline dev. |
| Geocoding | Google Places Text Search via `googlemaps` | Cached per-name JSON (`backend/geocode_cache.json`). |
| Storage | JSON artifact in `frontend/public/data.json` locally, `s3://beli-buzz-data/latest.json` remotely (public-read). |
| Delivery | AWS Lambda + EventBridge Cron (6am ET). Zip `backend/` & dependencies via `pip install -t`. |
| Frontend | React + Vite + `@vis.gl/react-google-maps` | Static app served on Cloudflare Pages hitting the public JSON. |

## Local development

### Backend (daily job)

1. `cd backend`
2. `cp .env.example .env` and fill in API keys (Gemini, Reddit, Google Maps, AWS optional).
3. `python3 -m venv venv && source venv/bin/activate`
4. `pip install -r requirements.txt`
5. Run the pipeline with mock data to refresh the local JSON:

```bash
python main_job.py --mock-data --output ../frontend/public/data.json --log-level DEBUG
```

When credentials are present omit `--mock-data` to hit live APIs and optionally add `--upload` to push straight to S3.

### Frontend

1. `cd frontend`
2. `pnpm install`
3. Copy `.env.example` (create one if none) and add `VITE_GOOGLE_MAPS_API_KEY` plus `VITE_TRENDING_DATA_URL` (defaults to `/data.json`).
4. Start Vite:

```bash
pnpm dev
```

Visit `http://localhost:5173` to see the Buzz map powered by the freshly generated JSON.

## Deployment guide

1. **S3 bucket** – `aws s3 mb s3://beli-buzz-data` (or console). Enable public-read on `latest.json` via bucket policy or per-object ACL.
2. **Lambda** – Zip `backend/` with `pip install -r requirements.txt -t package/`, point handler to `main_job.main`, set env vars + IAM role allowing `s3:PutObject`. Memory 512 MB, timeout 3 min.
3. **EventBridge** – Create rule `cron(0 11 * * ? *)` (6am ET) targeting the Lambda.
4. **Cloudflare Pages** – Connect repo, set build command `pnpm install && pnpm build` inside `frontend/`, output directory `frontend/dist`. Add env `VITE_TRENDING_DATA_URL=https://beli-buzz-data.s3.amazonaws.com/latest.json` and `VITE_GOOGLE_MAPS_API_KEY`.

## Cost snapshot

| Service | Notes | Est. monthly |
| --- | --- | --- |
| Cloudflare Pages | Static hosting | $0 |
| AWS Lambda | Single 2-3 minute run daily | ≈ $0 (free tier) |
| AWS S3 | Sub-10 KB JSON | <$0.01 |
| Google Maps | < 28k map loads | Free ($200 credit) |
| Gemini Flash | Within free tier |

## Next steps

- Harden RSS parsing per source (custom selectors, dedupe logic).
- Persist historical snapshots for trendlining.
- Add simple sanity tests (pytest) for analyzer prompts & scoring heuristics.
