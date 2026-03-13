# ReZone Live (NYC Demo)

Live-data office-to-housing feasibility demo for New York City.

## Stack

- Frontend: Next.js + Mapbox GL (`frontend`)
- Backend: FastAPI (`backend`)
- Live providers:
  - NYC PLUTO (office properties)
  - NYC Zoning FeatureServer (zoning polygons)
  - Transitland (transit stops, proxy ridership)
  - Overpass API (utility infrastructure proxies)

## Local Run

1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## API Additions

- `GET /api/buildings?bbox=minLng,minLat,maxLng,maxLat&limit=200&offset=0`
- `GET /api/layers?bbox=minLng,minLat,maxLng,maxLat&layers=office_buildings,zoning_districts,utility_infrastructure,transit_stops`
- `POST /api/feasibility-check` now returns `data_confidence` plus source/proxy transparency on utility/transit objects.

## Deploy

### Render (Backend)

- Create service from this repo, root directory `backend`.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Set env vars from `backend/.env.example`.

### Vercel (Frontend)

- Import `frontend` directory as project.
- Set env vars from `frontend/.env.example`.
- `NEXT_PUBLIC_API_URL` should point to Render backend URL.

