#!/data/.gvenv/bin/python
import json, csv, re
OUT='/data/property-agents/output'
zt=json.load(open('/data/property-agents/data/zone_tables.json'))['zones']
rows=json.load(open(f'{OUT}/parcels_overlay.json'))
def base(c): return re.sub(r'-\d+.*$','',(c or '').split('(')[0])
def oldfam(o):
    o=(o or '').upper()
    for k in ('R.1','R.2','R.3','R.4'):
        if o.startswith(k): return k
    return o.split('-')[0].split('(')[0]
cands=[]
for r in rows:
    b=base(r['new']); z=zt.get(b)
    if b not in ('RM.5','RM.6','RH.7') or not z or r['area_m2']<2000: continue
    if (r['owner'] or '').upper()!='PRIVATE': continue
    ha=r['area_m2']/10000; lo,hi=ha*z['density_uph_min'],ha*z['density_uph_max']
    of=oldfam(r['old'])
    tier={'R.1':'A','R.2':'A','UR':'A','R.3':'B','R.4':'C'}.get(of,'D')
    # tier A = low-density old -> medium/high new (biggest legal jump); B/C = multi-res already; D = other old zones (commercial/inst/etc.)
    cands.append({**r,'new_base':b,'old_family':of,'tier':tier,'units_min':round(lo),'units_max':round(hi),
                  'site_specific': bool(re.search(r'-\d',r['new'] or '') or re.search(r'-\d',r['old'] or ''))})
cands.sort(key=lambda c:(c['tier'],-c['units_max']))
json.dump(cands,open(f'{OUT}/upgrade_candidates.json','w'),indent=1)
cols=['tier','address','pin','old','new','area_m2','units_min','units_max','site_specific','lat','lon']
with open(f'{OUT}/upgrade_candidates.csv','w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(cands)
from collections import Counter
print('candidates (private, >=2000 m2, new RM.5/RM.6/RH.7):',len(cands))
print(Counter(c['tier'] for c in cands))
for t in 'ABCD':
    sub=[c for c in cands if c['tier']==t]
    print(f'\n== Tier {t}: {len(sub)} parcels, total max units {sum(c["units_max"] for c in sub)}')
    for c in sub[:12]:
        print(f'  {c["address"][:34]:<34} {c["old"]:<10}->{c["new"]:<8} {c["area_m2"]:>6} m2  {c["units_min"]}-{c["units_max"]} u  PIN {c["pin"]}')
