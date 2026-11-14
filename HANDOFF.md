# DukaanPulse — HANDOFF (source of truth)

_Last updated: 2026-11-14 (Groq LLM for reason + assistant chat; category-correct festival reasons; added cold-weather items blankets/heaters; data ends today 2026-11-14)._

## 1. What we are building

**DukaanPulse** — an **AI-powered purchase-planning assistant** for small Indian merchants who **already use POS software**. The merchant's POS is the source of truth; DukaanPulse is a **read-only analytics layer** that answers: *what to buy, how much, when, and which products are slow-moving / tying up money.*

Originally this repo was a **standalone inventory-management app** (kirana). It was **pivoted**: all POS-billing / manual-inventory functionality was removed and replaced by a simulated POS dataset. **Do not rebuild the old app.**

Hackathon scope. Use **clearly-labelled simulated POS data**. No real POS/LLM/supplier integrations yet except where noted.

## 2. Tech stack & environment

- Backend: **Python + FastAPI** (venv at `backend/.venv`). Run with uvicorn.
- Frontend: **React + Vite** (`frontend/`). Node is installed **locally** at `tools/node/bin` (NOT on global PATH, no sudo on this machine).
- Data: CSV + JSON only. No DB, no Redis/Kafka/Docker.
- LLM: **Groq chat** (`openai/gpt-oss-120b`, OpenAI-compatible, plain httpx) powers the "See detailed reason" feature and the screen 6 text Q&A (`backend/assistant.py`, key from `GROQ_API_KEY` in `backend/.env`). If no key is set, both fall back to deterministic replies.
- Env: Linux, shell bash.

**Run commands**
```bash
# backend (port 8000)
cd backend && .venv/bin/uvicorn main:app --port 8000            # add --reload for dev
# frontend (port 5173) — Node is local, so prefix PATH
cd frontend && PATH="$PWD/../tools/node/bin:$PATH" npm run dev
# both at once
./dev.sh
# tests
cd backend && .venv/bin/python -m unittest discover -s tests -v
# rebuild demo data (deterministic)
backend/.venv/bin/python backend/generate_demo_pos.py
# validate data integrity
backend/.venv/bin/python backend/validate_pos_data.py
```

**Gotchas learned**
- `npm`/`node` are **not** global; always prefix `PATH="$PWD/../tools/node/bin:$PATH"` (or use `dev.sh`). A `.bashrc` PATH line already exists for interactive shells.
- `--reload` is NOT used by default, so **the backend must be restarted after backend edits**. Restarting via the Agent Manager tool once caused a "port in use" race — stop, confirm the port is free, then start.
- A `freeport [port]` function + `freep` alias was added to `~/.bashrc` to kill a process holding a port (default 8000). `.bashrc` returns early for non-interactive shells, so `source` it in an interactive shell.

## 3. Project structure (key files)

Backend (`backend/`):
- `main.py` — FastAPI app; all **read-only** endpoints (see §5).
- `generate_demo_pos.py` — deterministic (seed `20261114`) generator for the simulated POS export.
- `validate_pos_data.py` — data-integrity checker (reconciliation, referential integrity, duplicates, pending-order rules).
- `pos_data.py` — ingestion/normalisation layer (reads CSVs once, caches, filtering helpers, `source_info`).
- `recommendations.py` — **the recommendation engine** (see §4).
- `tests/test_demo_pos.py` — 39 unittest tests (data + API + recommendations + weather/seasonality + adjustment layer).
- `requirements.txt` — fastapi, uvicorn[standard], httpx.
- `data/demo_pos_export/*` — simulated POS data: `products.csv, sales.csv, purchase_receipts.csv, suppliers.csv, purchase_orders.csv, stock_adjustments.csv, inventory_snapshot.csv, weather.csv, manifest.json`.

Frontend (`frontend/src/`):
- `App.jsx` — app shell: sidebar + header + **hash routing** (`#overview #recommendations #insights #budget #plan #assistant`), mobile drawer.
- `store.jsx` — `AppProvider`/`useApp`: loads status/products/inventory/suppliers/purchase-orders/recommendations; holds **purchase plan + budget** in `localStorage`; `useInr()`.
- `api.js` — fetch wrapper; `BASE = import.meta.env.VITE_API_BASE_URL` (empty in dev → Vite proxy). Methods for all POS endpoints + `recommendations()` + `budgetPlan(budget)`.
- `format.js` — display helpers: `dailyRate` (whole number, `<1` for slow movers), `wholeDays`, `dayPhrase`, `shortDate`.
- `services/` — `posService.js`, `recommendationService.js` (prefers real backend, falls back to fixtures), `assistantService.js` (deterministic demo replies), `speech.js` (Web Speech API hooks).
- `mocks/demoData.js` — **fallback-only** fixtures + `ASSISTANT_SUGGESTIONS`.
- `components/` — `Sidebar, Header, DataTable, StatusBadge, Metric, Section, StateView`.
- `pages/` — `Overview, Recommendations, InventoryInsights, BudgetPlanner, PurchasePlan, Assistant`.
- `styles.css` — full design system.

## 4. Recommendation engine (`backend/recommendations.py`)

Deterministic Python. Config: `ANALYSIS_WINDOW_DAYS=30`, `TARGET_COVER_DAYS=14`, `SAFETY_DAYS=3`, `SLOW_MOVING_MAX_VELOCITY=1.5`. "As of" date = latest sales date in the dataset (keeps output deterministic).

Per product computes: `velocity_per_day` (units in last 30 days / 30, **rounded to 1 decimal** — must stay decimal internally: slow movers divide by it), `days_remaining`, `stockout_risk` (none/low/medium/high/out_of_stock), `reorder_point`, `reorder_quantity` (MOQ-aligned), `reorder_cost`, `revenue_at_risk`, `tied_capital`, `slow_moving`.

**Action classification (added this session)** — drives wording + filtering:
- `order_now` — `days_remaining <= lead_time` (runs out before delivery).
- `order_soon` — `days_remaining <= lead_time + SAFETY_DAYS`.
- `plan_ahead` — `days_remaining <= lead_time + cover_days`.
- `no_action` — otherwise (excluded from the reorder list).
Also returns `order_by_date` and `expected_stockout_date` (ISO dates).

Functions: `product_metrics()`, `reorder_recommendations()` (includes order_now/order_soon/plan_ahead, ranked by action→revenue-at-risk→urgency), `slow_moving_products()`, `budget_plan(budget)` (greedy, MOQ-aligned partials, returns items/spent/remaining/skipped), `overview()` (summary + reorder_list + slow_moving + all products).

**Core decision inputs (user asked, confirmed):** sales history + current inventory + supplier lead time/MOQ + cost price. Purchase history/pending orders inform supplier behaviour but the buy/when/how-much math is those four.

**Adjustment layer (added this session)** — scales the baseline reorder quantity by demand signals, measured from the merchant's own data (not guessed):
- `season` — the product's month index (units in that month on non-festival days / its overall non-festival daily average).
- `festival` — calendar boosts, matched **per product**: a festival boost key is either a category (e.g. "Snacks") or a product-name keyword (e.g. "Thekua", "Sugarcane"), so reasons stay believable (a chocolate is not tied to Chhath; thekua and fruits are). See `festival_multiplier` in the generator and `_upcoming_festival_boost` in the engine. Look-ahead is `FESTIVAL_LOOKAHEAD_DAYS = 50`, covering next-month festivals. Near (<=10 days) reads "X is close", further reads "X is coming up".
- `temperature` — measured lift by temp bucket, applied **only** to weather-sensitive items: cold drinks, hot drinks, and cold-weather goods (blankets, heaters). Buckets: cool <20C, mild 20-30C, hot >=30C, so November reads "cool weather". This avoids a month/temperature confound.
- These are averaged over the upcoming coverage window (`lead + cover_days`), multiplied, then clamped to `[ADJUST_MIN=1.0, ADJUST_MAX=2.0]`, and re-aligned up to MOQ. So `reorder_quantity` is now the final (adjusted) number; the old number is kept as `baseline_reorder_quantity`, with `adjustment_multiplier` and a plain `adjustment_reason` string. Thin-data products fall back to category-level indices (`THIN_DATA_OVERALL`).
- Reorder ranking uses `adjustment_multiplier` as a tie-break after action, so items with the strongest demand signal (festival, then season/temperature) surface first.
- Wording rules hold: whole numbers, no em dash, reason says "Normal demand expected" when nothing changed.

## 5. API endpoints (all read-only)

- `GET /api/health`
- `GET /api/demo-pos/status` — source metadata + counts + `validation_ok`
- `GET /api/pos/products` (`category, supplier_id, ids`)
- `GET /api/pos/inventory` (`product_id`)
- `GET /api/pos/sales` (`start, end, product_id, limit`)
- `GET /api/pos/purchase-receipts` (`supplier_id, product_id, start, end`)
- `GET /api/pos/suppliers`
- `GET /api/pos/purchase-orders` (`status, supplier_id, product_id`)
- `GET /api/pos/stock-adjustments` (`product_id`)
- `GET /api/pos/weather` (`start, end`) — simulated daily temperature/rain aligned to the sales period
- `GET /api/recommendations` (`window_days, cover_days`) — summary/reorder_list/slow_moving/products
- `GET /api/recommendations/budget` (`budget, window_days, cover_days`)
- `GET /api/recommendations/reason` (`product_id`) — two-layer "why": returns a detailed plain-English reason for one recommendation. Uses **Groq chat** (`openai/gpt-oss-120b`, OpenAI-compatible, plain httpx) if `GROQ_API_KEY` is set (env or `backend/.env`; see `backend/.env.example`), otherwise a deterministic explanation (`source`: `llm` or `demo`). No hardcoded keys; `LLM_BASE_URL`/`LLM_MODEL` optional. See `backend/assistant.py`. Note: gpt-oss is a reasoning model, so no `max_tokens` cap is sent (a small cap returns empty).
- `POST /api/assistant/ask` (`{ "question": str }`) — free-text store Q&A for the assistant screen. Grounds the LLM in engine facts (summary, top reorders, slow movers, and, when the question contains a budget, the engine's `budget_plan`). Returns `{answer, source}`. Read only (no data mutated). The frontend prefers the LLM answer and falls back to the deterministic assistant when `source != "llm"`.

List responses: `{ "source": "simulated_demo_pos", "count": n, "items": [...] }`. Interactive docs at `/docs`.

## 6. Frontend screens (all six built & visually verified)

1. **Business Overview** — 4 clickable metric tiles (Stockout risk→recommendations `urgent`; Purchase requirement→budget; Slow-moving value→insights; Need attention→recommendations `all`); "Priority actions"; stockout table; slow-moving + recent recommendations.
2. **Purchase Recommendations** — metrics (Order now / Plan ahead / Estimated cost), filters (All/Urgent/Monitor/Low priority mapped to `action`), table incl. **Order by** column, per-product detail panel + "Add to Purchase Plan".
3. **Inventory Insights** — slow-selling table (+category filter), "More stock than needed" (fast sellers you are overstocked on, slow sellers excluded), disclaimers.
4. **Budget Planner** — budget input, ranked plan with include/qty edit, summary, over-budget warning, "couldn't fit" list.
5. **Purchase Plan** — editable table, remove, add-from-recommendations, supplier-wise totals, **Save Draft** (localStorage), "Draft only" note.
6. **Ask DukaanPulse** — chat with insight blocks + nav links, suggestions, mic (Web Speech), speak toggle, graceful voice fallback. Text answers now come from the backend LLM (`POST /api/assistant/ask`) when configured, with the deterministic assistant as fallback. Voice is browser-side only.

## 7. User preferences, constraints & corrections (IMPORTANT)

- **Do not** build a second POS; no manual sales/inventory editing, no billing.
- **Frontend-first** when asked; **do not modify the backend** unless the task says so.
- **One step at a time**; explain what/why/files, implement, verify, stop for approval.
- No unnecessary infra (no Kafka/Redis/Docker/microservices/vector DB).
- Do not hardcode API keys; use env vars with fallbacks.
- **No AI-looking design**: no purple/blue gradients, glassmorphism, glowing effects, giant rounded cards, oversized headings, fake charts, emoji-heavy UI, "a card for everything".
- Palette: green `#176B55`, bg `#F7F8F6`, surface `#FFFFFF`, text `#202923`, muted `#68736D`, border `#E4E8E4`, muted amber, restrained red. Font: system UI.
- **Numbers display as whole numbers** (user request): average daily sales → whole number (`<1` for slow movers), days → whole number. Stock already whole. (Implemented **display-only** in `format.js`; the engine keeps full precision.)
- **No em dash "—"** in user-facing text (user said it "looks AI"). Use periods/commas; empty values show `N/A`.
- **Bold the key parts** of recommendation sentences (action directive + order quantity).
- Keep recommendation wording **consistent with the action** (earlier there was a bug where text said "No immediate order required" then showed an order quantity).
- Show data-source honestly: "Demo Store", "Demo POS data connected (simulated, read-only)"; store name is a neutral fallback (no real merchant named).
- Preserve existing working code; don't leave demo test transactions in the data (regenerate if needed).

## 8. Progress status

**Completed & verified**
- Step 0: simulated POS data foundation + validation (reconciliation holds; pending orders excluded from stock) — `validate_pos_data.py` PASSED, files deterministic.
- Step 1: recommendation engine + `/api/recommendations`, `/api/recommendations/budget`.
- Frontend: all six screens; hash routing; responsive (mobile drawer verified); AI-look design avoided.
- Display fixes: whole-number daily sales & days; em dash removal; bold key recommendation text.
- Overview/Insights consistency fix: the Overview "Slow-moving value" tile previously showed `summary.tied_capital_total` (capital in **all** stock, e.g. ₹2,69,086), so it disagreed with Inventory Insights which summed only slow movers (₹12,948). Added `summary.slow_moving_tied_capital` in the engine as the single source and pointed both screens at it; label is now "Slow-moving value" on both. `tied_capital_total` still means whole-inventory capital. New test guards that the field equals the slow_moving list sum and never exceeds the total.
- Recommendation messaging: action-based with order-by & stockout dates.
- Data foundation: 1 year of sales (365 days) with seasonality + temperature + festival effects baked into the generator, plus `weather.csv` and `/api/pos/weather`. Tests: 42/42 OK. `npm run build` clean.
- Two-layer reason: `GET /api/recommendations/reason` + a "See detailed reason" button in the Recommendations detail panel. Returns `source: "llm"` when Groq is configured (verified live with `openai/gpt-oss-120b`), otherwise `source: "demo"` (deterministic). "No order needed" items always use the short deterministic line. The reason prompt requires the detailed answer to give the "why" (festival/weather/season) and the usual-vs-new quantity, and to say "running out now" when stock lasts under a day. Tests force the demo path (no network).
- Assistant Q&A (text only): `POST /api/assistant/ask` wires screen 6 to the LLM, grounded in engine facts (and the engine budget plan when a budget is in the question). Frontend prefers the LLM answer, falls back to the deterministic assistant. Verified live.
- Festival handling is now category-correct and look-ahead aware: reasons only name festivals that boost the product's own category (e.g. Dairy Milk, Britannia Good Day, Amul Butter -> "Chhath Puja is close"; Nescafe -> "mild weather, demand up"; Kurkure -> "November is a bigger month"), and festival items rank on top.
- Adjustment layer surfaced in the UI: Recommendations table has a "Why this much" column; the detail panel shows "Order this much (up from N)" and "Why this much"; Overview priority actions show a "Why more: ..." line when the quantity was raised.
- Adjustment layer: baseline reorder quantities scaled by measured season/festival/temperature multipliers (clamped [1.0, 2.0], MOQ-aligned), with `baseline_reorder_quantity`, `adjustment_multiplier`, `adjustment_reason` on each product. Engine and API verified live.
- Plain-English wording pass: "slow-moving" replaced with "slow-selling" (items that sell slowly); "Products that may run out" instead of "Products at stockout risk"; removed remaining em dashes from visible text (Recommendations detail sentences, Inventory Insights note) and switched `N/A` fallbacks to match §7. Overview tiles now use plain words: "May run out", "Money to restock", "Slow sellers", "Items to reorder" (was "Stockout risk", "Purchase requirement", "Slow-selling stock", "Need attention").
- De-duplication pass: the old Inventory Insights "High stock cover" table (days >= 45) only ever matched slow sellers, so it was a duplicate of the slow-selling list. It is now "More stock than needed": fast sellers only (slow sellers excluded), days cover >= 21. On Overview, sections were repeating products: removed the "Products that may run out" table (identical to the urgent "Priority actions"), renamed the top-5 table to "More recommendations" showing the next items, and made the recommendation lists exclude slow sellers so a product appears in exactly one Overview section.

**Verified working but note stale-server caveat:** these were verified against the running backend on :8000 (restart after backend edits).

**In progress / not started**
- **Current weather via API** — decided provider: **Open-Meteo** (free, no API key, current + historical + forecast). Not implemented yet; must be read-only with an env-var override and a fallback.
- **AI assistant backend (LLM)** — done (text only): screen 6 chat uses `POST /api/assistant/ask` (Groq) with a deterministic fallback. No audio yet; voice (Web Speech in the browser) is separate and unchanged. Possible next: stream tokens, add conversation history to the LLM call, or voice.
- Assistant is not wired to real data beyond the recommendation payload; budget question computes a live plan client-side.
- No auth/multi-tenant; single simulated store.
- Purchase-plan "Save Draft" is localStorage only.

**Unanswered / pending question**
- The user was asked which backend piece to build next and replied **"i will analyze it and let u know."** So: do not assume; ask/confirm before building the LLM backend.

## 9. Known bugs / limitations / gotchas

- Backend needs a **manual restart** after edits (no `--reload`); a stale server will serve old code and cause confusing results.
- `main.py` previously had a **name-shadowing bug** (a route handler named `inventory` shadowed the `inventory` module) — fixed by renaming to `get_inventory`. Watch for similar shadowing.
- React **Rules of Hooks**: `InventoryInsights` once crashed (blank page) because `useMemo` ran after early `return`s — fixed by moving all hooks above returns. Keep hooks unconditional.
- Local Node PATH requirement (see §2).
- No headless browser screenshots pipeline is part of the app; screenshots were captured with `geckodriver` (WebDriver HTTP) and saved under `screenshots/`.

## 10. Demo data notes (do not corrupt)

- **365 days** item-level sales (2025-11-15 to 2026-11-14), 5 suppliers (lead times 1–5 days, MOQ/MOV varied), 627 receipts, 633 purchase orders (**6 pending**), 17 adjustments, **365 daily weather rows**.
- 53 products. Added categories **Seasonal** (`Fleece Blanket Single`, `Room Heater 2000W`, sold more when cold), **Fruits** (`Sugarcane 1kg`, `Banana (dozen)`, `Coconut (whole)`), and **Sweets** (`Thekua 500g`). Festival boosts can target a **category OR a product-name keyword**, so Chhath boosts exactly the believable items (Thekua, Sugarcane, Coconut, Banana, Amul Milk, Curd) and not chocolate. `Room Heater 2000W`, `Sugarcane 1kg`, `Thekua 500g` are showcase-low so they rise to the top.
- Demo data includes **Chhath Puja (16 Nov, forward-looking)** plus two **showcase stock adjustments** (Nescafe and Dairy Milk left low; Colgate kept well covered). Chhath boosts only **Confectionery (sweets/thekua) and Dairy (milk for prasad)**, so the festival reason is believable (sweets/dairy), while biscuits/snacks show season only. All recorded as normal adjustments, so the accounting still reconciles.
- The data now ends on **2026-11-14 ("today")**, matching the snapshot timestamp (`2026-11-14T23:59:00`) and the engine "as of" date, so urgent items say "Order by 14 Nov" not a past date. If "today" moves, update `END_DATE`/`GENERATED_AT` in the generator and regenerate.
- **Seasonality + temperature are baked into the generator** (still one fixed seed `20261114`, fully deterministic): a monthly retail index (festive Oct-Nov high, monsoon Jul dip), festival windows (Diwali, Holi, Raksha Bandhan, Christmas, etc.) boosting festive categories, and a Delhi-like daily temperature series that drives cold drinks up when hot and tea/coffee up when cold. Regenerating reproduces identical files.
- Invariant: `opening + received − sales + adjustments = snapshot`; pending POs NOT in stock.
- Regenerate with the seeded generator (deterministic) — do **not** hand-edit CSVs.

## 11. Not a git repo

This directory is **not** a git repo (confirmed earlier). No commits/branches to preserve; `.gitignore` exists for when it becomes one. Preserve files on disk.

## 12. Instructions for the Next AI

```
Read HANDOFF.md in the project root FIRST (it is the source of truth). Then:
1. Inspect the current project: backend/ (main.py, recommendations.py, pos_data.py,
   validate_pos_data.py, tests/), frontend/src/ (App.jsx, store.jsx, services/, pages/),
   and backend/data/demo_pos_export/.
2. Respect all decisions and user preferences in HANDOFF.md §7 (whole-number display,
   no em dashes, bold key text, no AI-looking design, read-only backend, one step at a time).
3. Preserve existing code and unfinished changes. Do NOT rebuild the old standalone
   inventory app or add a second POS.
4. Continue from the documented next step. The pending item is the AI assistant backend
   (LLM) — but the user said "i will analyze it and let u know", so CONFIRM with the user
   before starting it. Do not start large new features unprompted.
5. Do not repeat completed work (Step 0 data + Step 1 engine + all six screens are done)
   or previously failed approaches (Rules-of-Hooks after early return; module/handler
   name shadowing; assuming --reload is on) without a good reason.
6. Ask the user only when an essential detail is missing.
7. Run verification: `cd backend && .venv/bin/python -m unittest discover -s tests` and
   `cd frontend && PATH="$PWD/../tools/node/bin:$PATH" npm run build`. Restart the backend
   after backend edits. Update HANDOFF.md whenever significant progress is made.
```

---

_If any detail here cannot be verified against the code, trust the code and note the discrepancy._
