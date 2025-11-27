# DAW Drug Search Alignment – 2025-11-19

Author: GPT-5.1 Codex  
Status: Drafted mid-session to capture current understanding and required fixes.  
Purpose: Replace older/out-of-sync notes so we can resume work quickly if the devcontainer disconnects.

---

## 1. Current Symptoms

- `/search` returns irrelevant drugs (low similarity) and shows `0.00%` because the Redis query always runs as `*=>[KNN …]`.
- Claude prompt only emits a bag-of-words string; no structured filters are fed into Redis, so hybrid search is effectively disabled.
- UI lists every NDC/dosage/packaging as a separate row, so a single drug can consume all visible slots.
- Alternatives vs. exact matches are indistinguishable; providers cannot tell why a result appears.
- UX lacks the nested “formats/strengths/package counts” drawer shown in the legacy app screenshots.

---

## 2. Target Architecture (confirmed with user)

1. **Prompt & Parser**
   - Use the `MEDICAL_SEARCH_SYSTEM_PROMPT` + template from `docs/IMPLEMENTATION_PLAN.md §4.1`.
   - Expected JSON shape:
     ```jsonc
     {
       "search_text": "...",        // embedding input
       "filters": {
         "drug_class": "...",
         "indication": "...",
         "drug_type": "...",
         "is_generic": "...",
         "dea_schedule": "...",
         "dosage_form": "...",
         "ndc": "...",
         "gcn_seqno": "..."
       },
       "corrections": ["orig → fix"],
       "confidence": 0.0-1.0
     }
     ```
   - Claude must return valid JSON; fallback path shows “No results found.”

2. **Redis Hybrid Search**
   - TEXT fields: `drug_name`, `brand_name`, `generic_name`.
   - TAG fields: `ndc`, `indication`, `drug_class`, `dosage_form`, `is_generic`, `dea_schedule`.
   - NUMERIC: `gcn_seqno`.
   - VECTOR: `embedding`.
   - Handler merges doctor-provided filters with Claude-derived ones (doctor input wins).
   - Build lexical clause from `search_terms` so literal matches (e.g., “Ozempic”) stay at the top.
   - Append KNN clause after filters: `(<text/tag clauses>)=>[KNN k @embedding $vec AS score]`.

3. **Result Semantics**
   - `/search` should return one entry per drug family (brand or generic grouping), not per NDC.
   - Each family indicates whether it is an *Exact Match* (query hit, same NDC) or an *Alternative* (same class/GCN).
   - `/drugs/{ndc}/alternatives` remains the deterministic “show therapeutic equivalents” endpoint when a provider needs a focused list.
   - `/drugs/{ndc}` remains the Aurora detail endpoint the UI calls when a row is expanded.

---

## 3. UX Requirements (from screenshots & discussion)

1. **Result List (max 20 rows)**
   - Row: Med name, generic name, type (Brand/GN), manufacturer status, match badge.
   - “Select” button opens detail drawer.
   - Heart icon or similar for favorites can be stubbed later.

2. **Detail Drawer**
   - Header: drug summary, class/indication text.
   - Tabs or sections: Formats, Allergies, Current Meds (future).
   - Formats list:
     - Strengths (e.g., 5 mg, 10 mg).
     - Expanding a strength shows specific package counts/SIG templates (e.g., “30 tablets – take 1 daily”).
   - Formulary indicators (Active/Inactive) mirrored from existing system if data available.

3. **Debug / Demo Info**
   - Show Claude’s `search_terms`, applied filters, corrections, confidence.
   - If no Redis hits, display “No results found” in UI and propagate the backend message.

---

## 4. Implementation Tasks

1. **Prompt Module**
   - Add `daw_functions/src/prompts/medical_search.py` with the §4.1 prompt text and template helpers.

2. **Claude Integration**
   - Update `expand_query_with_claude()` to use the new prompt, parse JSON, and return structured data + metrics.
   - Gracefully handle JSON errors; log raw output for debugging.

3. **Handler Changes (`functions/src/search_handler.py`)**
   - Merge doctor filters and Claude filters.
   - Derive text tokens for Redis TEXT clause.
   - Pass both text tokens and filters into `redis_hybrid_search`.
   - Include structured info in `query_info` for clients.

4. **Redis Query Builder**
   - Accept `text_terms`, `filters`, `limit`.
   - Build TEXT clause per token (escaped, grouped across `drug_name|brand_name|generic_name`).
   - Add TAG clauses for every schema field; normalize casing to match ingest.
   - Allow numeric filtering on `gcn_seqno`.
   - Return metadata (`applied_filters`, `text_clause`, actual query string).

5. **Result Grouping**
   - Group Redis documents by canonical drug (likely `gcn_seqno` + `brand_name/generic_name`).
   - Attach deduplicated list of NDCs + strengths + package options via Aurora lookup or precomputed map.

6. **Frontend Updates**
   - Update `drug-search.tsx` to consume the new payload, show structured filters/terms, match badges, and “No results” state.
   - Implement grouped rows + drawer UI similar to screenshots (possibly reusing shadcn accordion/drawer components).

7. **Documentation & Memory**
   - Keep this file as the authoritative status for 2025-11-19.
   - After implementation, update:
     - `docs/DAW_ARCHITECTURE_OVERVIEW.md` (search flow section).
     - `docs/NEXT_SESSION_2025_11_17.md` or newer session log.
     - `memory-bank/activeContext.md` and `progress.md`.

---

## 5. Risks & Open Questions

1. **Data completeness**: Current Redis load may lack populated `indication` / `drug_class` TAGs; confirm loader pipeline.
2. **Grouping key**: Need clear rule (GCN vs. brand) to avoid mixing unrelated combos.
3. **Performance**: Additional TEXT clauses could reduce recall if the prompt emits overly specific tokens—may need fuzzy fallback.
4. **LLM failures**: Decide whether to skip search or fall back to plain text expansion if Claude emits invalid JSON.
5. **Alternatives badge**: Need deterministic logic (likely `same_gcn_seqno` vs. `same_class`) to flag entries.

---

## 6. Next Concrete Steps

1. Implement the prompt module + handler parsing changes (Claude → JSON).
2. Expand Redis query builder with TEXT/TAG gating and diagnostics.
3. Add result grouping in the handler response and surface structured info to the UI.
4. Update frontend layout (grouped rows, drawer, match/alternative badges, “No results found” state).
5. Validate with sample queries (“ozempic”, “rosuvastatin”, “statin for high cholesteral”).
6. Refresh docs/memory once features are live.

---

## 7. Implementation Progress (2025-11-19 evening update)

- ✅ **Prompt module + parser** — `daw_functions/src/prompts/medical_search.py` added; `expand_query_with_claude()` now enforces JSON schema and exposes structured metadata in `query_info`.
- ✅ **Redis query builder & grouping** — `redis_hybrid_search()` accepts text terms + filters, emits lexical/TAG clauses, and returns grouped medication families with match labels, similarity %, and variant lists.
- ✅ **Frontend alignment** — `frontend/app/components/drug-search.tsx` consumes the new payload, displays Claude insights, badges exact vs alternative, and collapses dosage formats to prevent duplicate rows.
- ✅ **Diagnostics UX** — Query interpretation card now includes a toggle that shows the exact Claude JSON payload for debugging/demo.
- ✅ **Claude fallback + sane filters** — If the LLM ever returns invalid JSON, we gracefully fall back to plain expansions instead of 500s. Automatic TAG filters are currently disabled (pending data backfill), so only doctor-provided filters are enforced while the lexical gate + vector KNN drive relevance.
- ⏳ **Outstanding** — Validate real-world queries, audit Redis TAG data, hook “Select” action to `/drugs/{ndc}` + `/drugs/{ndc}/alternatives`, and design the full detail drawer (formats + sig templates).

---

## 8. Current Issues, Causes, and Planned Resolutions

| Issue | Observed Behavior | Root Cause | Resolution Status |
| --- | --- | --- | --- |
| Claude occasionally returns plain text (no JSON) | Handler threw 500s before fallback | Prompt-only approach can emit non-JSON despite instructions | Tool-use schema with Bedrock Converse (per [AWS blog](https://aws.amazon.com/blogs/machine-learning/structured-data-response-with-amazon-bedrock-prompt-engineering-and-tool-use/)) – in progress |
| Literal drug not ranked first (Ozempic vs semaglutide) | Semantic twins can outrank the requested brand | Lexical clause is a pure OR + cosine score tie | Update query builder to AND literal tokens before synonym ORs and boost exact matches – planned |
| Rosuvastatin search shows only “ROSUVASTATIN CALCIUM 5 MG TAB” duplicates | No distinct CRESTOR vs ROSUVASTATIN rows; 20 identical 5 mg entries | Redis currently stores one doc per NDC and grouping uses `gcn_seqno`, so generic entry represents entire family | Build “family” docs (brand vs generic) from existing Redis hashes using `is_generic`, `BN`, `GNN60`, strengths, manufacturer status; search returns separate rows per family with formats list – planned |
| TAG filters over-constrain results | Claude-derived indication filter can zero out matches | `indication` data is incomplete in Redis | Auto-apply disabled (doctor filters still honored) – done |
| Formats drawer lacks strength hierarchy | Each variant row equals single NDC | Need aggregation of strengths/packages | Will add when building family docs |

---

## 9. ✅ CRITICAL FIX APPLIED - Brand/Generic Grouping (2025-11-19 Evening)

### Problem
Search for "ROSUVASTATIN" only showed generic results. CRESTOR (brand) was hidden because grouping logic merged therapeutic equivalents into single families.

### Investigation Findings (Direct Redis Queries)
- ✅ Redis has `brand_name="CRESTOR"` for brand drugs
- ✅ Redis has `is_generic=false` for CRESTOR  
- ✅ Redis has `is_generic=true` for ROSUVASTATIN CALCIUM
- ✅ Both share `gcn_seqno=51784` (10mg - therapeutic equivalents)
- ✅ **ALL DATA EXISTS IN REDIS** - No Aurora reload needed (GPT Codex was wrong)

### Root Cause
```python
# OLD (WRONG): Merged brands and generics into one group
group_key = doc.get('gcn_seqno')  # CRESTOR + ROSUVASTATIN → same group!
```

### Solution Applied
```python
# NEW (CORRECT): Separates brand families from generic families
if is_brand and brand_name:
    group_key = f"brand:{brand_name}"       # e.g., brand:CRESTOR
else:
    group_key = f"generic:{gcn_seqno}"      # e.g., generic:51784
```

### Expected Results After Fix
**Search "ROSUVASTATIN"** returns TWO separate families:
1. **ROSUVASTATIN CALCIUM** (generic family, exact match, all strengths)
2. **CRESTOR** (brand family, alternative match, all strengths)

**Search "CRESTOR"** returns TWO separate families:
1. **CRESTOR** (brand family, exact match, primary)
2. **ROSUVASTATIN CALCIUM** (generic family, alternative, generic equivalent)

**Files Changed:** `functions/src/search_handler.py` lines ~508-574  
**Full Documentation:** `docs/2025-11-19_GROUPING_FIX.md`  
**Status:** ✅ Fixed and ready for deployment testing

---

Keep this document open while working—if the container drops, reload this file to regain context. If major decisions change, create a new dated file and link back here for history.

