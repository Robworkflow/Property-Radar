# Layer-2 "is it still available?" check — findings (Oct 23 2026)
Method tested: web_search `"<address>" Guelph development OR proposal OR sale` per VACANT/UNDERBUILT candidate (39), keep only results whose text contains the street number (or a range containing it). Results in output/web_check.json.
- guelph.ca scraping is WAF-blocked for scripts (403) and the browser tool isn't installed; the active-development-files category page has only ~18 items — weak source. Use web_search/web_extract tools (agent-side), not urllib.
- Gordon St (Tricar) CAUGHT: 1250, 1260, 1270 all returned city planning docs naming the 1242-1270 assembly that GIS missed.
- Keyword verdict (TAKEN/NO-EVIDENCE) is TOO CRUDE: 22/39 flagged TAKEN, many from old Committee-of-Adjustment minutes, MLS listings, unrelated PDFs. Misses real ones too (1156 Paisley returned NO-EVIDENCE although a search surfaced active file OZS24-015/OZS25-014 for four apartment buildings).
- 7 candidates had no address in the address layer -> UNCHECKED (need parcel-centroid reverse lookup).
=> Search retrieves evidence; an LLM (Scorer agent) must READ it and decide TAKEN / OPEN / UNCLEAR. Do not automate the verdict with keywords.
