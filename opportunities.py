#!/data/.gvenv/bin/python
"""Combine zoning overlay + existing-use check -> VACANT / UNDERBUILT / IN-PLAY / BUILT lists."""
import json,csv,re
OUT='/data/property-agents/output'
zt=json.load(open('/data/property-agents/data/zone_tables.json'))['zones']
rows=json.load(open(f'{OUT}/parcels_overlay.json')); use=json.load(open(f'{OUT}/parcel_use.json'))
def base(c): return re.sub(r'-\d+.*$','',(c or '').split('(')[0])
def oldfam(o):
    o=(o or '').upper()
    for k in ('R.1','R.2','R.3','R.4'):
        if o.startswith(k): return k
    return o.split('-')[0].split('(')[0]
out=[]
for r in rows:
    b=base(r['new']); z=zt.get(b)
    if (r['owner'] or '').upper()!='PRIVATE' or r['area_m2']<1000: continue
    u=use.get(f"{r['pin']}|{r['gpid']}")
    if not u or not z or 'density_uph_min' not in z: continue   # unit-capped RL zones handled separately
    ha=r['area_m2']/10000
    tier={'R.1':'A','R.2':'A','UR':'A','R.3':'B','R.4':'C'}.get(oldfam(r['old']),'D')
    if u['dev_apps']: cat='IN-PLAY'
    elif u['bldg_n']==0: cat='VACANT'
    elif u['coverage_pct']<=8: cat='UNDERBUILT'   # few/small structures (house/shed on big lot)
    else: cat='BUILT'
    out.append({**r,'category':cat,'tier':tier,'new_base':b,'units_min':round(ha*z['density_uph_min']),'units_max':round(ha*z['density_uph_max']),
        'bldg_n':u['bldg_n'],'coverage_pct':u['coverage_pct'],'dev_apps':'; '.join(f"{a['FOLDERDESC']} {a['REFERENCEFILE']} ({a['STATUSDESC']})" for a in u['dev_apps']),
        'condo_pin':r['pin'].endswith('0000'),'site_specific':bool(re.search(r'-\d',r['new'] or '') or re.search(r'-\d',r['old'] or ''))})
# adjacency: a parcel touching/within 25 m of a parcel with an active dev app may be part of the same assembly
import sys; sys.path.insert(0,'/data/property-agents')
from property_recon import download_layer, PROP
from shapely.geometry import shape
from shapely.strtree import STRtree
pf=download_layer(PROP,'PIN,GPID','parcels')
geo={f"{(f.get('properties') or {}).get('PIN') or ''}|{(f.get('properties') or {}).get('GPID') or ''}":shape(f['geometry']) for f in pf if f.get('geometry')}
inplay=[c for c in out if c['category']=='IN-PLAY']
for c in out:
    c['near_app']=''
    if c['category']=='IN-PLAY': continue
    g=geo.get(f"{c['pin']}|{c['gpid']}")
    if g is None: continue
    for ip in inplay:
        g2=geo.get(f"{ip['pin']}|{ip['gpid']}")
        if g2 is not None and g.distance(g2)*111320*0.72<25:
            c['near_app']=f"next to {ip['address'][:25]} {ip['dev_apps'][:40]}"; break
# 2nd hop: assembly chains (e.g. 1242 -> 1250 -> 1260/1270)
hop1=[c for c in out if c['near_app'] and c['category']!='IN-PLAY']
for c in out:
    if c['category']=='IN-PLAY' or c['near_app']: continue
    g=geo.get(f"{c['pin']}|{c['gpid']}")
    for h in hop1:
        g2=geo.get(f"{h['pin']}|{h['gpid']}")
        if g is not None and g2 is not None and g.distance(g2)*111320*0.72<25:
            c['near_app']='2 hops: '+h['near_app'][:50]; break
out.sort(key=lambda c:(-c['units_max']))
json.dump(out,open(f'{OUT}/opportunities.json','w'),indent=1)
cols=['category','tier','address','pin','old','new','area_m2','bldg_n','coverage_pct','units_min','units_max','dev_apps','near_app','condo_pin','site_specific','lat','lon']
for cat in ('VACANT','UNDERBUILT','IN-PLAY','BUILT'):
    sub=[c for c in out if c['category']==cat]
    with open(f'{OUT}/opps_{cat.lower()}.csv','w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(sub)
from collections import Counter
print(Counter(c['category'] for c in out))
for cat in ('VACANT','UNDERBUILT','IN-PLAY'):
    sub=[c for c in out if c['category']==cat]
    print(f'\n== {cat}: {len(sub)} parcels')
    for c in sub[:12]:
        print(f"  [{c['tier']}] {c['address'][:30]:<30} {c['old']:<9}->{c['new']:<8} {c['area_m2']:>6}m2 cov={c['coverage_pct']}% {c['units_min']}-{c['units_max']}u {c['dev_apps'][:40]} {c['near_app'][:50]}")
print('\nTricar check:')
for c in out:
    if re.search(r'12(42|50|60|70) Gordon',c['address']): print('  ',c['address'],c['category'],c['dev_apps'] or c['near_app'] or '-')
print('vacant+underbuilt with NO nearby app:',sum(1 for c in out if c['category'] in('VACANT','UNDERBUILT') and not c['near_app']))
