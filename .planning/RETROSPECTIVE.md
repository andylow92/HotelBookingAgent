# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-18
**Phases:** 5 | **Plans:** 5

### What Was Built
- Pydantic v2 data models matching README JSON schemas (shared/models.py)
- Defensive scoring engine with 5-dimension normalization and weighted formula (scorer.py)
- Amadeus Hotel API client with automatic mock data fallback (api_client.py)
- Search pipeline with ranking, tagging, and re-score capability (search.py)
- Action router with dispatch dict and in-memory booking store (agent.py)
- Travel-advisor-tone negotiation notes with concrete numeric comparisons (scorer.py)

### What Worked
- Single-plan-per-phase structure kept execution fast and focused
- Mock data fallback decision up-front ensured demo reliability
- Plan checker caught real bugs before execution (key collision in read response, wrong python path in verify commands)
- Discuss-phase captured just enough decisions without over-specifying

### What Was Inefficient
- ROADMAP.md progress table wasn't updated by phase-complete CLI (stale data throughout)
- Summaries lacked one-liner fields, making accomplishment extraction manual
- Phase 1 had no discuss-phase (context gathered retroactively) — later phases benefited from the discuss step

### Patterns Established
- Dispatch dict pattern for action routing (extensible for future actions)
- `(response, raw_data)` tuple return pattern for caching upstream data
- Module-level state for hackathon simplicity (resets on restart)
- Travel-advisor tone for user-facing text generation

### Key Lessons
1. Plan checker warnings are worth fixing before execution — saves debugging time in executor
2. Small phases (1 plan, 1-2 tasks) execute more reliably than large ones
3. Discuss-phase is valuable even for "obvious" phases — it surfaces edge cases (free_cancellation refund logic, read response key collision)

### Cost Observations
- Model mix: sonnet for verification/plan-checking, inherit (default) for execution/research/planning
- Sessions: 1 continuous session for full milestone
- Notable: 5 phases completed in ~1 hour of wall-clock time

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 5 | 5 | Initial project — established discuss→plan→execute→verify cycle |

### Top Lessons (Verified Across Milestones)

1. Plan checker catches real implementation bugs — always run it
2. Small focused phases execute faster than large ambitious ones
