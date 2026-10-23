#!/data/.gvenv/bin/python
"""Parcel-level overlay: every Guelph parcel -> old zone, new zone, lot area, address; rank upgrade candidates.
Read-only. Uses cached zoning layers from property_recon.py; downloads parcel + address layers once."""
import json, os, re, csv, sys
sys.path.insert(0, '/data/property-agents')
from property_recon import download_layer, BASE_OLD, BASE_NEW, ADDR, PROP, meters_area, OUT
from shapely.geometry import shape
from shapely.strtree import STRtree

def props(f): return f.get('properties') or f.get('attributes') or {}

def build_index(feats, field_list):
    items = [(shape(f['geometry']), props(f)) for f in feats if f.get('geometry')]
    return STRtree([g for g, _ in items]), items

def lookup(idx, items, pt, key):
    for j in idx.query(pt):
        if items[j][0].contains(pt):
            p = items[j][1]
            for k in key:
                if p.get(k): return p[k]
    return None

if __name__ == '__main__':
    old = download_layer(BASE_OLD, 'ZONE1', 'old_zoning')
    new = download_layer(BASE_NEW, 'ZONING_CODE,ZONE_1', 'new_zoning')
    parcels = download_layer(PROP, 'PIN,GPID,OWNERSHIP,PARCELSTAT', 'parcels')
    addrs = download_layer(ADDR, 'ADDRESS,PIN,LAT,LONG', 'addresses')
    print(len(old), len(new), len(parcels), len(addrs))
    oi, oitems = build_index(old, ['ZONE1']); ni, nitems = build_index(new, ['ZONING_CODE'])
    from shapely.geometry import Point
    addr_by_pin = {}
    for a in addrs:
        p = props(a)
        if p.get('PIN') and p.get('ADDRESS'): addr_by_pin.setdefault(str(p['PIN']), []).append(p['ADDRESS'])
    rows = []
    for f in parcels:
        if not f.get('geometry'): continue
        g = shape(f['geometry']); p = props(f)
        pt = g.representative_point()
        o = lookup(oi, oitems, pt, ['ZONE1']); n = lookup(ni, nitems, pt, ['ZONING_CODE', 'ZONE_1'])
        pin = str(p.get('PIN') or '')
        rows.append({'pin': pin, 'gpid': p.get('GPID'), 'owner': p.get('OWNERSHIP'), 'status': p.get('PARCELSTAT'),
                     'address': '; '.join(addr_by_pin.get(pin, [])[:3]), 'old': o, 'new': n,
                     'area_m2': round(meters_area(g)), 'lat': round(pt.y, 6), 'lon': round(pt.x, 6)})
    json.dump(rows, open(f'{OUT}/parcels_overlay.json', 'w'))
    print('parcels classified:', len(rows), 'no new zone:', sum(1 for r in rows if not r['new']))
