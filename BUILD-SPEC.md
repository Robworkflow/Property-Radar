# Property Opportunity Agent Team — Build Spec (v0, Oct 23 2026)
Purpose: find Guelph properties where the 2023 zoning (By-law 2023-20790) allows far more than the 1995 zoning did, are still available, and are lower-capital / faster to act on. Off-market postal outreach only; a human approves every letter; the zoning upside is never revealed to owners.
Status key: PROVEN = built and tested on real data | PARTIAL | NOT BUILT | BLOCKED.

## 1. Design principle (proven)
Scripts MEASURE (deterministic, free, repeatable). Agents JUDGE (read evidence, decide, cite). Keyword automation of judgement failed (22/39 false "TAKEN"); an LLM reading the evidence worked. Never let a script decide availability.

## 2. Pipeline and roles
| # | Stage / role | Status | Implementation | Input -> Output |
|---|---|---|---|---|
| 1 | Zoning Analyst | PROVEN (gate test: Cedar St 100%) | zoning_analyst.py, zoning-analyst-prompt.md, data/zone_tables.json | address/street -> old zone, new zone, density gap |
| 2 | Scout: city-wide overlay | PROVEN | property_recon.py --city | zoning layers -> output/city_overlay_summary.json |
| 3 | Scout: parcel overlay | PROVEN (43,273 parcels) | parcel_overlay.py | parcels+zones+addresses -> output/parcels_overlay.json |
| 4 | Scout: existing-use check | PROVEN | building_check.py | buildings(38,944)+active dev apps(307) -> output/parcel_use.json |
| 5 | Scout: categorise + rank | PROVEN | opportunities.py (VACANT/UNDERBUILT/IN-PLAY/BUILT), small_opps.py (target list) | -> output/opps_*.csv, small_opps.{csv,json} |
| 6 | Scorer | PROVEN on 22 parcels | scorer-agent-prompt.md; run via delegate_task | one parcel -> output/scored/<PIN>.json |
| 7 | Packager (decision sheet) | NOT BUILT | - | scored/*.json -> grouped, ranked review pack |
| 8 | Path analyst (how to acquire) | BLOCKED | - | needs ownership + MLS data (see gaps) |
| 9 | Outreach drafts | NOT BUILT | rules written | -> /data/outreach/drafts/ (human approves) |
| - | Supervisor / scheduler / operations | NOT BUILT | Paperclip (adapter unproven) | orchestrates the above |
(Rob's team is 9 roles; confirm the exact names/split before wiring Paperclip.)

Target definition (small_opps.py): private lot 500-2,000 m2, existing buildings, not condo (PIN not ending 0000), old R.1/R.2/UR -> new RM.5/RM.6/RH.7/RL.4, no active application on the parcel. Vacant land is parked (low priority: capital + time). Bigger-lot filters (>=2,000 m2) skew to land/apartment sites.

## 3. Data contracts (what each stage reads/writes)
- parcels_overlay.json rows: pin, gpid, owner, status, address, old, new, area_m2, lat, lon
- parcel_use.json keyed "PIN|GPID": bldg_n, bldg_m2, coverage_pct, dev_apps[]
- small_opps.json rows add: old_family, new_base, units_min/max (bylaw ceiling), net_gain_max, near_app, site_specific, zone_full, holding
- scored/<PIN>.json: verdict (TAKEN | OPEN-PROVISIONAL | OPEN | UNCLEAR), confidence, flags[], checks_done{city_docs,address_pin,neighbour_assembly,listing}, evidence[{claim,url,date}], neighbours_in_play[], manual_checks[], summary, next_action (drop|watch|verify-by-human|prep-mail-draft)
Join key = PIN (parcels/addresses); parcel->zone uses representative-point containment (a parcel straddling two zones gets one).

## 4. Data sources
Free/proven: Guelph Open Data ArcGIS (OpenData1: zoning 9, buildings 10, ActiveDevelopmentPlanning 27, parcels 16, addresses 0; OpenData2/16 new zoning). Layers cache to /data/cache/scratch/zoning (pruned after ~24h idle; re-download is automatic, minutes). Web search/extract reach guelph.ca PDFs (notices, planning reports, council agendas).
Not reachable: guelph.ca HTML pages (403 to scripts; Cloudflare check also stops the browser tool) — heritage register, GPAS permit/application search; MLS/realtor sites; title/ownership. Do not try to defeat bot protection.

## 5. Traps found (each needs a standing check)
1. Holding symbols: zone string RM.5(PA)(H12) — H12 = no NEW residential until City confirms municipal services adequate (staff removes routinely; provision under appeal). The code was being stripped; 47/100 targets carry it. Now carried as `holding`/`zone_full`. Unit ceilings are conditional on removal.
2. Application point layer flags ONE lot of an assembly (Tricar 1242 flagged; 1250/1260/1270/9 Valley missed). Adjacency (25 m, 2 hops) helps but misses 3-hop chains; only document search catches the rest. Scorer must always do a neighbour-assembly search.
3. Buildings layer is aerial-sourced and lags new builds/demolitions.
4. Unit counts = bylaw density x lot area: a ceiling, not approvable (setbacks, parking, servicing ignored). Existing units unknown (assumed ~1).
5. By-law 2023-20790 is IN FORCE (Feb 2024); only parts are under OLT appeal (OLT-23-000462; decision issued May 29 2026 — NOT yet read for the RM/RH zones). Where appealed, stricter of old/new applies. One agent wrongly said "not in force".
6. Old zone UR -> RM.5 (Watson Pkwy N) is real in the City layer but unverified at Official Plan level.
7. 7 candidates had no address in the address layer (need centroid reverse lookup).
8. RL.3 density cell unreadable in the PDF (marked VERIFY).

## 6. Runtime limits
- Model: OpenRouter, anthropic/claude-sonnet-5.5, new-account limit 20 requests/min. 5 parallel subagents all failed (HTTP 429); 2 in parallel works (~1.5-3 min per 5-6 parcels). Scoring N parcels ~ N x 3-5 searches.
- Interpretation work must run on the frontier model; config changes apply to NEW sessions.
- Browser tool agent-browser installed (works on normal sites; blocked by guelph.ca).
- Standing rule: ask Rob before restarting services or changing config.

## 7. Gaps / decisions for Rob (these drive the infrastructure pass)
1. OWNERSHIP + LISTING DATA (biggest): title/ownership (GeoWarehouse/Teranet or via realtor/lawyer) and MLS access. Blocks Path analyst + Outreach. Options: paid API, realtor feed, or a manual step per shortlisted cluster.
2. Rate limit: backup provider (`hermes fallback add`) or higher tier — decides how many agents run at once.
3. Paperclip + hermes-paperclip-adapter: UNPROVEN. Verify against the real repo before install; check it honours HERMES_HOME=/data (it reads ~/.hermes by default). $200/month cap would live in Paperclip, not in Hermes config (no `budget` key exists). Several commands proposed by another LLM were invented (`paperclipai plugin install`, `hermes skills sync`, `hermes config set budget.*`).
4. GitHub: repo for /data/property-agents (currently local git only, 12 commits, no remote). Decide private repo, what is committed (outputs contain public GIS data only; no secrets).
5. Skills: property-opportunity-research skill holds the method; decide one skill per agent role vs one umbrella.
6. Scheduling: when/how often the pipeline refreshes (layers change; applications are added weekly).
7. Confirm the 9 role names and which are human-in-the-loop.

## 8. Current results snapshot
22 parcels scored: 3 TAKEN (1260 Gordon, 9 Valley Rd, 1170 Gordon), 14 OPEN-PROVISIONAL (Watson Pkwy N x7, Bagot 124/126, Arkell 82/88, Gordon 1152/1160, 7 College W, 148 Fleming), 5 UNCLEAR (1236 Gordon, 64 Harts, 72 Harts, 28 Roland, 267 Bristol). All 14 carry (H12). Nothing is confirmed available until ownership/MLS is checked.

## 9. Ownership data — OnLand dry test (Oct 23 2026) — gap #1 partially solved
- onland.ca (public, guest checkout, no licence). Flow worked with the browser tool: choose LRO 61 Guelph/Wellington -> Property -> PIN (block 5 digits + property 4 digits, e.g. 713330072 -> 71333 / 0072) -> "Requested by" (max 20 chars) -> result.
- Search is FREE and returns: status (Active), land-titles type, address, legal description. It confirmed our engine's PIN -> address join (71333-0072 = 104 Elizabeth St).
- OWNER NAMES require buying the Parcel Register: $33.40 before HST (~$37.74 with HST) per PIN, 1 page. Not purchased; stopped before the cart. Payment must be entered by Rob (no card entry by the agent).
- Search hours: Mon-Thu 4am-midnight, Fri to 9pm, Sat 9-6, Sun 9-9 ET.
- Not yet checked: OnLand terms of service on automated use -> keep human-in-the-loop. GeoWarehouse ($3,900+/yr) break-even ~100 lookups/yr; eligibility for non-professionals unknown.
- Listing/sold status: free consumer sites (HouseSigma/Zolo/Zoocasa) read via browser; no official MLS feed; not yet tested.

## 10. Decisions logged (Rob, Oct 23 2026)
- Ownership names (gap #1): RESOLVED as a manual step — Rob's partner holds a GeoWarehouse licence and supplies owner info free on request. Not automatable (licence is the partner's); the agents only produce the PIN/address list to send him. No OnLand purchases.
- Contact/mailing-address gathering + owner-occupied vs rented check: SHELVED for the Scorer agent build (not now).
- Vacant land: low priority (separate list only).
- Next phase: infrastructure alignment (GitHub, Paperclip, skills, rate limit, schedule, 9 roles).
