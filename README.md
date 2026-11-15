# DukaanPulse

**Live demo: https://dukaanpulse.onrender.com**

DukaanPulse is a read only purchase planning assistant for small Indian shops
that already bill through a POS system. The POS owns the data. DukaanPulse reads
the shop's own sales record and answers the three questions a shopkeeper faces
every week: what to buy, how much, and when.

## The problem

A small shopkeeper decides what to buy from memory and gut feel. That leads to
two kinds of loss. Fast selling items run out, so the shop loses sales it could
have made. Slow selling items sit on the shelf and lock up the shop's money.
There is no simple tool that turns the shop's own sales data into a clear buying
decision.

## What it does

- **Reorder suggestions.** For each product, how much to order and by when,
  based on sales speed, stock on hand, supplier lead time and pack size.
- **Demand signals.** The quantity is adjusted for the month, upcoming festivals
  and the weather, so it matches what is actually likely to sell.
- **Slow selling items.** The products that are quietly tying up money.
- **Budget planner.** A prioritised buy list for a given rupee budget.
- **Purchase plan.** A working list the shopkeeper builds and saves.
- **AI assistant.** One recommendation can be explained in detail, and the chat
  answers store questions in plain English.

The AI never does the maths. It only explains the numbers the engine computes.

## How it works

Three layers, each with one job.

```
  POS export (CSV)        the shop's own sales record, the only input
        |
        v
  Engine (Python)         computes every number: what to reorder, how much, when
        |
        v
  Web app (React)         the six screens the shopkeeper uses
```

The backend is read only. There is no database and no write path, so the POS
stays the single source of truth and DukaanPulse can never change it.

## Screens

1. Overview
2. Recommendations
3. Inventory Insights
4. Budget Planner
5. Purchase Plan
6. Ask DukaanPulse

## Tech

FastAPI and Python for the engine and API, React and Vite for the web app. Data
is plain CSV and JSON, no database. The AI layer is optional (Groq) and falls
back to clear deterministic replies when no key is set.

## Demo data

The POS export in this repo is fully simulated and deterministic, so the demo is
safe to share. It holds 53 products, one year of item level sales, 5 suppliers
and daily weather, with seasonality, festival and temperature effects baked in.
It is a hackathon project, not connected to any real shop.
