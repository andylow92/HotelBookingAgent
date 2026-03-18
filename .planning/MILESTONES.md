# Milestones

## v1.0 MVP (Shipped: 2026-03-18)

**Phases completed:** 5 phases, 5 plans
**Python LOC:** 1,043 across 8 files
**Timeline:** 3 days (Mar 15–18, 2026)
**Requirements:** 15/15 satisfied

**Key accomplishments:**
1. Pydantic v2 data models matching README JSON schemas with full validation (shared/models.py)
2. Defensive scoring engine — 5-dimension normalization, weighted formula, edge case guards (scorer.py)
3. Amadeus Hotel API integration with automatic mock data fallback on any failure (api_client.py)
4. Search pipeline with score_and_rank, top-3 tagging, and re-score without re-fetching (search.py)
5. Action router dispatching search/book/read/cancel via dispatch dict with in-memory booking store (agent.py)
6. Travel-advisor-tone negotiation notes with concrete price/distance/rating comparisons (scorer.py)

---

