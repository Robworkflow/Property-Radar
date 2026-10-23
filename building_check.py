#!/data/.gvenv/bin/python
"""Existing-use check: for every parcel -> building count, building footprint area, coverage %, active development applications.
Buildings layer = OpenData1/10 (aerial-sourced, may lag); ActiveDevelopmentPlanning = OpenData1/27 (points).
Output: output/parcel_use.json (keyed by pin/gpid) and re-ranked output/opportunities.{json,csv}"""
import json, sys, csv, re
sys.path.insert(0,'/data/property-agents')
from property_recon import download_layer, BASE_OLD, PROP, OUT, meters_area
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
B='https://gismaps.guelph.ca/hosting/rest/services/OpenData/OpenData1/FeatureServer'
def props(f): return f.get('properties') or f.get('attributes') or {}
if __name__=='__main__':
    bl=download_layer(f'{B}/10','NAME,GPID,BLDID,SOURCE','buildings')
    dev=download_layer(f'{B}/27','ADDRESS,FOLDERDESC,FOLDERTYPE,STATUSDESC,FOLDERDESCRIPTION,REFERENCEFILE,SUBDESC,INDATE','active_dev')
    parcels=download_layer(PROP,'PIN,GPID,OWNERSHIP,PARCELSTAT','parcels')
    print(len(bl),len(dev),len(parcels))
    bg=[shape(f['geometry']) for f in bl if f.get('geometry')]
    bt=STRtree(bg)
    dpts=[(shape(f['geometry']),props(f)) for f in dev if f.get('geometry')]
    dt=STRtree([g for g,_ in dpts])
    use={}
    for f in parcels:
        if not f.get('geometry'): continue
        g=shape(f['geometry']); p=props(f)
        key=str(p.get('PIN') or '')+'|'+str(p.get('GPID') or '')
        n=0; ba=0.0
        for j in bt.query(g):
            inter=bg[j].intersection(g)
            if inter.is_empty: continue
            a=meters_area(inter)
            if a<5: continue          # sliver
            n+=1; ba+=a
        pa=meters_area(g)
        apps=[]
        for j in dt.query(g):
            if g.contains(dpts[j][0]) or g.intersects(dpts[j][0]):
                q=dpts[j][1]; apps.append({k:q.get(k) for k in ('FOLDERDESC','STATUSDESC','REFERENCEFILE','SUBDESC','FOLDERDESCRIPTION')})
        use[key]={'bldg_n':n,'bldg_m2':round(ba),'coverage_pct':round(100*ba/pa,1) if pa else None,'dev_apps':apps}
    json.dump(use,open(f'{OUT}/parcel_use.json','w'))
    print('parcels with use data:',len(use),'| no buildings:',sum(1 for u in use.values() if u['bldg_n']==0),'| with dev apps:',sum(1 for u in use.values() if u['dev_apps']))
