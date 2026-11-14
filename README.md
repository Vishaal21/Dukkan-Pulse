# DukaanPulse

A read-only purchase planning assistant for a small Indian shop. It reads a POS
export, computes what to reorder (how much and when), and explains the reasoning
in plain English. It also includes an AI assistant that answers store questions.

The POS owns the data. DukaanPulse only consumes it: every backend route is read
only, there is no database and no write path.

## What it does

- **Recommendations** - which products to reorder, how much, and by when, based on
  sales speed, stock on hand, supplier lead time and pack size.
- **Demand signals** - the reorder quantity is adjusted for month seasonality,
  upcoming festivals, and temperature (cold drinks and cold-weather goods).
- **Inventory insights** - slow-selling items (money stuck) and overstocked fast sellers.
- **Budget planner** - a prioritised buy plan for a given rupee budget.
- **Purchase plan** - a working list the shopkeeper builds and saves.
- **AI assistant** - one recommendation can be explained in detail, and the chat
  answers store questions, both written by an LLM when configured.

## Screens

1. Overview
2. Recommendations
3. Inventory Insights
4. Budget Planner
5. Purchase Plan
6. Ask DukaanPulse

## Architecture

```
  simulated POS export (CSV)        backend/ (FastAPI, read only)
  backend/data/demo_pos_export/  ->  pos_data        loads + caches the CSV export
                                     validate_...    integrity checks
                                     recommendations the engine (all numbers)
                                     assistant       optional LLM layer (Groq)
                                     main            read-only API routes
                                              |
                                              v
                                     frontend/ (React + Vite)
                                       store.jsx     loads once, caches
                                       services/     backend first, demo fallback
                                       pages/        the six screens
```

All figures are computed by the engine. The LLM never calculates; it only explains
the numbers it is given.

## Quick start

```
  ./dev.sh          # backend on http://127.0.0.1:8000, frontend on http://127.0.0.1:5173
```

Or start them separately:

```
  # backend
  cd backend && .venv/bin/uvicorn main:app --port 8000

  # frontend (uses the bundled node in tools/)
  cd frontend && PATH="$PWD/../tools/node/bin:$PATH" npm run dev
```

Then open http://localhost:5173.

Note: the backend does not auto-reload. Restart it after backend edits.

## AI model (optional)

The detailed reason and the assistant chat use **Groq** (`openai/gpt-oss-120b`,
OpenAI-compatible, called with plain httpx). The key is read from the environment
or from `backend/.env`:

```
  # backend/.env  (git-ignored)
  GROQ_API_KEY=your_key_here
  # optional:
  # LLM_BASE_URL=https://api.groq.com/openai/v1
  # LLM_MODEL=openai/gpt-oss-120b
```

If no key is set, both features fall back to a deterministic explanation, so the
app still works offline. See `backend/.env.example`. No keys are hardcoded.

## API (all read only)

```
  GET  /api/health
  GET  /api/demo-pos/status
  GET  /api/pos/products | inventory | sales | suppliers
  GET  /api/pos/purchase-orders | purchase-receipts | stock-adjustments | weather
  GET  /api/recommendations
  GET  /api/recommendations/budget?budget=10000
  GET  /api/recommendations/reason?product_id=P001
  POST /api/assistant/ask        { "question": "What should I reorder today?" }
```

## Data

The POS export is fully simulated demo data (not from Paytm, Zoho or any real
vendor). It is deterministic: one fixed seed reproduces identical files.

```
  53 products, 365 days of sales (2025-11-15 to 2026-11-14),
  5 suppliers, daily weather, plus seasonality, festival and temperature effects
```

Regenerate with the seeded generator (do not hand-edit the CSVs):

```
  cd backend && .venv/bin/python generate_demo_pos.py
```

The dataset is anchored to a fixed "today" of 2026-11-14. If the date moves on,
update `END_DATE` and `GENERATED_AT` in the generator and regenerate.

## Tests and build

```
  cd backend  && .venv/bin/python -m unittest discover -s tests
  cd frontend && PATH="$PWD/../tools/node/bin:$PATH" npm run build
```

## Project layout

```
  backend/
    main.py                read-only API routes
    recommendations.py     the engine (all numbers)
    pos_data.py            loads + caches the CSV export
    validate_pos_data.py   data integrity checks
    generate_demo_pos.py   seeded demo data generator
    assistant.py           optional LLM layer (Groq)
    data/demo_pos_export/  the simulated POS export
    tests/
  frontend/
    src/store.jsx          global state
    src/services/          backend first, demo fallback
    src/pages/             the six screens
    src/components/        shared UI
  HANDOFF.md               running build notes and decisions
```

See `HANDOFF.md` for the full history, decisions and remaining work.
