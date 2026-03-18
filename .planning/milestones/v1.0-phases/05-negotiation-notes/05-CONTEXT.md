# Phase 5: Negotiation Notes - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate human-readable tradeoff explanations between the top 3 scored hotel options. Notes explain price vs location vs rating tradeoffs specific to the actual search results. The note is a single string returned in the SearchResponse `negotiation_note` field.

</domain>

<decisions>
## Implementation Decisions

### Note tone & audience
- Travel advisor tone — warm, professional ("Hotel Adlon offers the best location at a premium, while...")
- Primary audience is Orca (the orchestrator agent) — notes help Orca explain options to the end user
- Include concrete numeric values from scoring (e.g., "€45/night cheaper", "0.8km closer", "rated 4.5 vs 3.8")
- Notes compare the top 3 tagged options (BEST_BALANCE, CHEAPEST, HIGHEST_RATED)

### Claude's Discretion
- Note length — adapt based on how different the options are (concise when similar, detailed when divergent)
- Exact sentence structure and flow
- Which dimensions to emphasize based on the user's weights
- How to handle edge cases (e.g., fewer than 3 options, ties)

</decisions>

<specifics>
## Specific Ideas

- Notes should feel like a knowledgeable travel advisor summarizing options, not a raw data dump
- Reference actual hotel names, prices, and distances — make it specific to the results
- The note lives in SearchResponse.negotiation_note (already an empty string field)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-negotiation-notes*
*Context gathered: 2026-03-18*
