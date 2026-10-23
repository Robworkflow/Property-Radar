# property-agents
Guelph property zoning-upside team (private). Start with BUILD-SPEC.md.
- Scripts measure (property_recon, parcel_overlay, building_check, small_opps); agents judge (scorer-agent-prompt.md).
- Kept in git: code, prompts, spec, results worth keeping (output/small_opps.*, output/scored/*, output/city_overlay_summary.json).
- NOT in git (regenerate with the scripts): big overlay/cache files. Never in git: owner names, mailing addresses, outreach drafts.
Run scripts with /data/.gvenv/bin/python. Order: property_recon.py --city -> parcel_overlay.py -> building_check.py -> small_opps.py -> scorer agent.
