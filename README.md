# Belly-Buzz 🍜

AI-powered Toronto restaurant discovery based on real conversations from Reddit and food blogs.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OFFLINE ETL PIPELINE                               │
│                        (Runs daily via cron)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │   SCRAPE     │───▶│   EXTRACT    │───▶│   ENRICH     │───▶│ VECTORIZE  │ │
│  │ Reddit/Blogs │    │  LLM (Groq)  │    │ Google Maps  │    │  OpenAI    │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └────────────┘ │
│                                                                      │       │
│                              ┌────────────────────────────────┐      │       │
│                              │         SCORE & STORE          │◀─────┘       │
│                              │   Supabase (PostgreSQL +       │              │
│                              │   pgvector)                    │              │
│                              └────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          REAL-TIME API PIPELINE                              │
│                       (Handles user requests)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │   Frontend   │───▶│   FastAPI    │───▶│  Embed Query │───▶│  Vector    │ │
│  │   (React)    │    │   Server     │    │   (OpenAI)   │    │  Search    │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Semantic Search**: Find restaurants using natural language ("best date night ramen spot")
- **Buzz Score**: AI-calculated score based on social engagement and sentiment
- **Real Data**: Scraped from Reddit (r/askTO, r/FoodToronto) and food blogs
- **Vector Search**: pgvector-powered similarity search with OpenAI embeddings
- **Google Maps Integration**: Verified location data and interactive map view

## Tech Stack

### Backend
- **FastAPI** - Python API framework
- **Supabase** - PostgreSQL database with pgvector extension
- **Groq** - LLM API (Llama 3.1) for entity extraction and sentiment analysis
- **OpenAI** - Embeddings API (text-embedding-3-small)
- **Google Maps API** - Location enrichment

### Frontend
- **React 19** + **TypeScript**
- **Vite** - Build tool
- **TanStack Query** - Data fetching and caching
- **Google Maps** - Interactive map
- **Tailwind CSS** - Styling

## Project Structure

```
belly-buzz/
├── backend/
│   ├── api/
│   │   ├── main.py           # FastAPI application
│   │   └── schemas.py        # API schemas
│   ├── etl/
│   │   ├── ingest.py         # ETL pipeline entry point
│   │   ├── scoring.py        # Buzz/Viral/Sentiment scoring
│   │   ├── enrichment.py     # Google Places enrichment
│   │   ├── scrapers/
│   │   │   ├── reddit.py     # Reddit scraper
│   │   │   └── blogs.py      # Blog scraper
│   │   └── llm/
│   │       └── extractor.py  # LLM entity extraction
│   ├── models/               # Shared Pydantic models
│   ├── embeddings.py         # OpenAI embeddings (shared)
│   ├── database/
│   │   └── schema.sql        # Supabase database schema
│   ├── Dockerfile
│   ├── render.yaml           # Render deployment config
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       └── types/
└── README.md
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm
- Supabase account
- API Keys: Google Maps, Groq, OpenAI

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Run the API server
uvicorn api.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
pnpm install
pnpm dev
```

### Run ETL Pipeline

```bash
cd backend
source venv/bin/activate
python -m etl.ingest
```

## Environment Variables

### Backend (.env)

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your-service-role-key

# Google Maps
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

# Groq (LLM for ETL)
GROQ_API_KEY=your-groq-api-key

# OpenAI (Embeddings)
OPENAI_API_KEY=your-openai-api-key
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_MAPS_API_KEY=your-google-maps-api-key
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/search` | Search restaurants with semantic similarity |
| GET | `/restaurants/{id}` | Get single restaurant |
| GET | `/trending` | Get trending restaurants |
| GET | `/cuisines` | List cuisine types |

### Search Parameters

```
GET /search?q=best%20ramen&price_min=1&price_max=3&sort_by=buzz_score
```

| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Natural language search query |
| `price_min` | 1-4 | Minimum price tier |
| `price_max` | 1-4 | Maximum price tier |
| `cuisine` | string[] | Filter by cuisine tags |
| `sort_by` | enum | buzz_score, sentiment_score, viral_score, rating |
| `sort_order` | enum | asc, desc |

## Deployment

### Render (recommended)

The `render.yaml` file configures both services:

- **API**: Web service running FastAPI
- **ETL**: Cron job running daily at 6 AM UTC

```bash
# Deploy via Render Dashboard or CLI
render blueprint apply
```

### Manual Docker

```bash
cd backend

# Build
docker build -t belly-buzz .

# Run API
docker run -p 8000:8000 --env-file .env belly-buzz

# Run ETL
docker run --env-file .env belly-buzz python -m etl.ingest
```

## License

MIT
