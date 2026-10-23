#!/data/.gvenv/bin/python
"""Lower-capital target: EXISTING buildings on 500-2000 m2 private lots where the zone family jumped
(old R.1/R.2/R.3(low) or UR -> new RM.5/RM.6/RH.7/RL.4) and no active development application. Ranks by units gained."""
import json,csv,re,sys
sys.path.insert(0,'/data/property-agents')
from property_recon import download_layer, PROP
from shapely.geometry import shape
OUT='/data/property-agents/output'
zt=json.load(open('/data/property-agents/data/zone_tables.json'))['zones']
zt['RL.4']={**zt['RL.4'],'density_uph_min':0,'density_uph_max':35}   # RL.4 = max 35 u/ha per bylaw table
rows=json.load(open(f'{OUT}/parcels_overlay.json')); use=json.load(open(f'{OUT}/parcel_use.json'))
def base(c): return re.sub(r'-\d+.*$','',(c or '').split('(')[0])
def fam(o):
    o=(o or '').upper()
    for k in ('R.1','R.2','R.3','R.4'):
        if o.startswith(k): return k
    return o.split('-')[0].split('(')[0]
cand=[];apps=[]
for r in rows:
    b=base(r['new'])
    if b not in ('RM.5','RM.6','RH.7','RL.4') or (r['owner'] or '').upper()!='PRIVATE': continue
    if not (500<=r['area_m2']<2000) or r['pin'].endswith('0000'): continue
    u=use.get(f"{r['pin']}|{r['gpid']}")
    if not u or u['bldg_n']==0: continue                    # existing buildings only (vacant parked)
    f=fam(r['old'])
    if f not in ('R.1','R.2','UR'): continue                # real family jump: low-density -> medium/high
    ha=r['area_m2']/10000; z=zt[b]
    umax=int(ha*z['density_uph_max']); umin=round(ha*z['density_uph_min'])
    cand.append({**r,'new_base':b,'old_family':f,'bldg_n':u['bldg_n'],'coverage_pct':u['coverage_pct'],'units_min':umin,'units_max':umax,
      'net_gain_max':umax-1,'dev_app':bool(u['dev_apps']),'site_specific':bool(re.search(r'-\d',r['new'] or '') or re.search(r'-\d',r['old'] or ''))})
# adjacency to any parcel with an app
pf=download_layer(PROP,'PIN,GPID','parcels')
geo={f"{(f.get('properties') or {}).get('PIN') or ''}|{(f.get('properties') or {}).get('GPID') or ''}":shape(f['geometry']) for f in pf if f.get('geometry')}
appg=[geo[k] for k,u in use.items() if u['dev_apps'] and k in geo]
for c in cand:
    g=geo.get(f"{c['pin']}|{c['gpid']}")
    c['near_app']=bool(g is not None and any(g.distance(a)*111320*0.72<25 for a in appg))
# holding symbols (H12 = municipal services adequate before new residential) live in ZONE_1 of the new layer; base() strips them
from shapely.geometry import Point
from shapely.strtree import STRtree
nf=[f for f in json.load(open('/data/cache/scratch/zoning/new_zoning.geojson')) if f.get('geometry')]
ng=[shape(f['geometry']) for f in nf]; nt=STRtree(ng)
for c in cand:
    pt=Point(c['lon'],c['lat']); c['zone_full']=None
    for j in nt.query(pt):
        if ng[j].contains(pt): c['zone_full']=(nf[j].get('properties') or {}).get('ZONE_1'); break
    h=re.findall(r'\(H\d*\)',c['zone_full'] or ''); c['holding']=h[0] if h else ''
cand=[c for c in cand if not c['dev_app']]
cand.sort(key=lambda c:(-c['net_gain_max'],c['area_m2']))
json.dump(cand,open(f'{OUT}/small_opps.json','w'),indent=1)
cols=['address','pin','old','new','area_m2','bldg_n','coverage_pct','units_min','units_max','net_gain_max','near_app','site_specific','zone_full','holding','lat','lon']
with open(f'{OUT}/small_opps.csv','w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(cand)
from collections import Counter
print('candidates:',len(cand),'| near an active app:',sum(c['near_app'] for c in cand),'| site-specific:',sum(c['site_specific'] for c in cand))
print('by jump:',Counter(f"{c['old_family']}->{c['new_base']}" for c in cand))
for c in cand[:20]:
    print(f"  {c['address'][:28]:<28} {c['old']:<8}->{c['new']:<7} {c['area_m2']:>5}m2 bldgs={c['bldg_n']} cov={c['coverage_pct']}%  up to {c['units_max']}u {'NEAR-APP' if c['near_app'] else ''}")
