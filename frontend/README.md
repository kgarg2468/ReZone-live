# ReZone Frontend

## Run

```bash
npm install
cp .env.example .env.local
npm run dev
```

Required env vars:

- `NEXT_PUBLIC_API_URL` (FastAPI backend URL)
- `NEXT_PUBLIC_MAPBOX_TOKEN`

The app fetches buildings/layers by current map bbox and computes feasibility via backend live scoring.

