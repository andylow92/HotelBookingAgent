# Phase 05: Negotiation Notes — Research

**Researched:** 2025-07-25
**Question:** What do I need to know to PLAN this phase well?

---

## 1. What Exists Today

### Target Field
`SearchResponse.negotiation_note` (str, defaults to `""`) — already defined in `shared/models.py:154`. Both `search()` and `rescore()` in `provider_agent/search.py` build a `SearchResponse` but never populate `negotiation_note`. The field ships empty to the consumer.

### Data Available at Generation Time
When `score_and_rank()` returns the top 3 `HotelOption` objects, each carries:

| Field | Type | Example |
|---|---|---|
| `name` | str | "Hotel Adlon Kempinski Berlin" |
| `price_per_night` | float | 189.0 |
| `rating` | float | 4.8 |
| `distance_km` | float | 0.2 |
| `free_cancellation` | bool | True |
| `amenities` | list[str] | ["wifi", "breakfast", "pool", …] |
| `total_score` | float | 0.87 |
| `score_breakdown` | ScoreBreakdown | price=0.59, location=0.94, … |
| `tag` | str \| None | "BEST_BALANCE" / "CHEAPEST" / "HIGHEST_RATED" |

The `Weights` object is also in scope (price, location, rating, cancellation, amenities — all 0–1, sum to 1.0).

### Where the Note Gets Consumed
Per README and CONTEXT: Orca (the orchestrator) reads `negotiation_note` to explain tradeoff reasoning to the end user. The note appears in the Orca trace dashboard during demos. The Consumer Agent may relay it verbatim or paraphrase it.

---

## 2. Integration Points

### Where to Generate
Two call sites need to populate `negotiation_note`:

1. **`provider_agent/search.py → search()`** — line 52, builds `SearchResponse` after `score_and_rank()`. The `request.weights` and ranked `options` are both in scope.
2. **`provider_agent/search.py → rescore()`** — line 75, same pattern. `weights` is a parameter; `ranked_options` is local.

Both functions already have everything needed. No model changes required.

### Module Placement
A new function (e.g., `generate_negotiation_note`) can live in:
- **Option A: `provider_agent/scorer.py`** — it operates on scored data and weights; logically adjacent to ranking/tagging.
- **Option B: New file `provider_agent/negotiation.py`** — isolates note generation, keeps scorer focused on math.

**Recommendation:** Option A is simpler (one fewer import, scorer already handles the ranked options). Note generation is ~30–50 lines, not enough to justify a separate module for a hackathon codebase.

### Caller Changes
Both `search()` and `rescore()` need one extra line each: call the generator, pass result to `SearchResponse(negotiation_note=...)`. No signature changes.

---

## 3. Note Generation Logic

### Inputs
```python
def generate_negotiation_note(
    options: list[HotelOption],  # top 3, already tagged
    weights: Weights,            # user's current preference weights
) -> str:
```

### Algorithm Outline

1. **Guard clause:** If `len(options) < 2`, return a brief note (single option = no tradeoff to explain). If `len(options) == 0`, return `""`.

2. **Identify the three roles** by tag:
   - `best` = option with tag `BEST_BALANCE` (always index 0)
   - `cheapest` = option with tag `CHEAPEST`
   - `highest_rated` = option with tag `HIGHEST_RATED`
   - Handle missing tags gracefully (e.g., only 2 results → no `HIGHEST_RATED`).

3. **Compute concrete deltas** between pairs:
   - Price diff: `cheapest.price_per_night - best.price_per_night` (e.g., "€27/night cheaper")
   - Distance diff: `abs(best.distance_km - cheapest.distance_km)` (e.g., "1.3km further")
   - Rating diff: `highest_rated.rating - best.rating` (e.g., "rated 4.8 vs 4.4")
   - Score diff: total_score deltas show how close/far options are overall

4. **Compose sentences** using the travel-advisor tone from CONTEXT:
   - Lead with the best-balance pick and why it scored highest
   - Compare the cheapest: what you gain (price savings) and lose (rating drop, location, etc.)
   - Compare the highest-rated: what you gain (rating, amenities) and lose (price premium)
   - Mention any stand-out dimension the user weighted heavily (use `weights` to detect emphasis)

5. **Adaptive length** (per CONTEXT "Claude's Discretion"):
   - When options are very similar (score spread < 0.05): short note ("All three options are closely matched…")
   - When options diverge significantly: detailed note with all deltas

### Example Output (Mock Data, Default Weights)
> "Hotel Indigo Berlin – Ku'damm offers the best balance at €105/night (rated 4.4, 0.8km out) with free cancellation. Generator Berlin Mitte is €47/night cheaper but drops to 3.4 stars, sits 1.0km further, and lacks free cancellation. Hotel Adlon Kempinski Berlin leads on rating (4.8) and location (0.2km) but costs €84/night more."

---

## 4. Edge Cases

| Scenario | Handling |
|---|---|
| **0 options** | Return `""` — no results, no note |
| **1 option** | "Only one option matched your criteria: {name} at €{price}/night." |
| **2 options** | Compare the two; skip the missing tag |
| **Tied tags** | `_assign_tags` already handles this — tags won't duplicate. If CHEAPEST == BEST_BALANCE (same hotel), only compare against HIGHEST_RATED |
| **Identical prices/ratings** | Mention "similarly priced" / "equally rated" instead of "€0 cheaper" |
| **Very large price gaps** | Use whole euros, no decimals (€47 not €47.00) |
| **distance_km = 0.0** (API data) | Omit distance comparison when both are 0.0 — not meaningful |

---

## 5. Weights-Aware Emphasis

The user's weights signal what they care about most. The note should mirror this:

| Heaviest Weight | Note Emphasis |
|---|---|
| `price` ≥ 0.35 | Lead with price comparisons, frame savings prominently |
| `location` ≥ 0.35 | Lead with distance comparisons |
| `rating` ≥ 0.35 | Lead with rating comparisons |
| `cancellation` ≥ 0.30 | Explicitly call out which options have/lack free cancellation |
| `amenities` ≥ 0.25 | Mention amenity overlap/gaps |

Threshold detection is simple: `max(weights.price, weights.location, ...)` → find dominant dimension → reorder sentences.

---

## 6. Formatting Conventions

- **Currency:** Use `€` prefix, whole euros for per-night prices (e.g., "€105/night")
- **Distances:** One decimal km (e.g., "0.8km"), drop "km" if it reads better ("0.8km out")
- **Ratings:** One decimal, out of 5 (e.g., "rated 4.4")
- **Names:** Full hotel name on first mention, can shorten to "the cheapest option" on subsequent
- **Score values:** Do NOT expose raw 0–1 scores in the note — users don't think in normalized scores. Translate to concrete values (prices, distances, stars)
- **Tone:** Warm, professional travel advisor. Not robotic, not overly casual.

---

## 7. Testing Approach

No formal test suite exists (out of scope per REQUIREMENTS.md). Manual verification:

1. Run with mock data + default weights → confirm note references correct hotel names, prices, distances
2. Run with price-heavy weights (0.55) → confirm note leads with price savings
3. Run with only 1 or 2 results → confirm edge case notes are sensible
4. Run rescore with changed weights → confirm note updates to reflect new ranking

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Note reads as raw data dump | Medium | High (defeats purpose) | Template approach with natural language connectors; review output manually |
| Note is stale after rescore | Low | Medium | Both `search()` and `rescore()` call the same generator |
| Note references wrong hotel for tag | Low | High | Generator reads tags from options, doesn't assume indices |
| Overly long note for similar options | Low | Low | Adaptive length based on score spread |

---

## 9. Implementation Scope Summary

| Item | File | Change Size |
|---|---|---|
| `generate_negotiation_note()` function | `provider_agent/scorer.py` | ~40–60 lines (new function) |
| Call in `search()` | `provider_agent/search.py` | 1–2 lines changed |
| Call in `rescore()` | `provider_agent/search.py` | 1–2 lines changed |
| Model changes | None | `negotiation_note: str = ""` already exists |

**Total estimated change:** ~50 lines of new code, ~4 lines modified. Single-plan phase.

---

## 10. Key Decisions for Planning

1. **Where does the function live?** → Recommend `scorer.py` (adjacent to ranking logic, avoids new file)
2. **String building approach?** → f-strings with conditional sections (no templates library needed)
3. **Note generation is deterministic** — pure function of options + weights, no randomness, no LLM call
4. **Both search paths must generate notes** — `search()` and `rescore()` call the same function

---

*Research complete. Ready for planning.*
