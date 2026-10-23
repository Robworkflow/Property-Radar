#!/data/.gvenv/bin/python
"""Property recon: city-wide old-vs-new zoning overlay + address one-pagers (Guelph).
Read-only against Guelph Open Data. Caches full layers to disk.
City overlay: for each NEW zoning polygon, find OLD polygon containing its rep point;
summarize (old->new) zone-pair changes by polygon count and area.
One-pagers: address -> old zone, new zone, family jump, PIN, lot area (m2), rough unit potential.
"""
import json, os, time, math, argparse, urllib.request, urllib.parse
from collections import defaultdict
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

OUT = '/data/property-agents/output'
os.makedirs(OUT, exist_ok=True)
CACHE = '/data/cache/scratch/zoning'
os.makedirs(CACHE, exist_ok=True)

BASE_OLD = 'https://gismaps.guelph.ca/hosting/rest/services/OpenData/OpenData1/FeatureServer/9'
BASE_NEW = 'https://gismaps.guelph.ca/hosting/rest/services/OpenData/OpenData2/FeatureServer/16'
ADDR     = 'https://gismaps.guelph.ca/hosting/rest/services/OpenData/OpenData1/FeatureServer/0'
PROP     = 'https://gismaps.guelph.ca/hosting/rest/services/OpenData/OpenData1/FeatureServer/16'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())

def download_layer(base, fields, cache_name):
    """fully page the layer as GeoJSON, cache to disk"""
    path = f'{CACHE}/{cache_name}.geojson'
    if os.path.exists(path):
        return json.load(open(path))
    feats, off = [], 0
    while True:
        q = urllib.parse.urlencode({'where': '1=1', 'outFields': fields,
                                    'resultRecordCount': 1000, 'resultOffset': off,
                                    'f': 'geojson', 'outSR': 4326})
        d = get(f'{base}/query?{q}')
        fs = d.get('features', [])
        feats += fs
        if len(fs) < 1000:
            break
        off += 1000
        time.sleep(0.2)
    json.dump(feats, open(path, 'w'))
    print(f'  cached {cache_name}: {len(feats)} features')
    return feats

def point_zone_attr(layer, lat, lon, field):
    q = urllib.parse.urlencode({'geometry': f'{lon},{lat}', 'geometryType': 'esriGeometryPoint',
                                'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects',
                                'outFields': field, 'f': 'json', 'outSR': 4326})
    d = get(f'{layer}/query?{q}')
    fs = d.get('features', [])
    if fs:
        return fs[0]['attributes']
    return None

def family(code):
    if not code: return None
    c = code.strip().upper()
    return c.split('-')[0].split('(')[0]

def meters_area(geom):
    """approximate planimetric area in m2 via local equirectangular transform (~43.55N)"""
    from shapely.ops import transform
    kx, ky = 111320.0, 111320.0 * math.cos(math.radians(43.55))
    t = transform(lambda x, y, z=None: (x * kx, y * ky) if z is None else (x * kx, y * ky, z), geom)
    return t.area

def city_overlay():
    print('CITY OVERLAY — downloading layers…')
    old_feats = download_layer(BASE_OLD, 'ZONE1', 'old_zoning')
    new_feats = download_layer(BASE_NEW, 'ZONING_CODE,ZONE_1', 'new_zoning')
    old_polys = [(shape(f['geometry']), f.get('properties', f.get('attributes', {})).get('ZONE1')) for f in old_feats if f.get('geometry')]
    old_geoms = [p for p, _ in old_polys]
    idx = STRtree(old_geoms)
    pairs = defaultdict(lambda: {'n': 0, 'area': 0.0})
    unmatched = 0
    for f in new_feats:
        g = f.get('geometry')
        if not g: continue
        ng = shape(g)
        new_code = f.get('properties', f.get('attributes', {})).get('ZONING_CODE') or f.get('properties', f.get('attributes', {})).get('ZONE_1')
        hit = idx.query(ng.representative_point())
        old_code = None
        for j in hit:
            p = old_geoms[j]
            if p.contains(ng.representative_point()):
                old_code = old_polys[j][1]
                break
        if old_code is None:
            unmatched += 1
            continue
        pairs[(str(old_code), str(new_code))]['n'] += 1
        pairs[(str(old_code), str(new_code))]['area'] += meters_area(ng)
    rows = sorted(pairs.items(), key=lambda kv: -kv[1]['n'])
    total_n = sum(v['n'] for _, v in rows)
    print(f'\nCITY OVERLAY SUMMARY — {len(rows)} distinct (old→new) pairs, {total_n} polygons, unmapped={unmatched}')
    print(f'{"OLD → NEW":<24} {"#polys":>7} {"km²":>8}')
    for (o, n), v in rows[:25]:
        print(f'{o:<22} {v["n"]:>7} {v["area"]/1e6:>8.2f}')
    with open(f'{OUT}/city_overlay_summary.json', 'w') as fh:
        json.dump({f'{o}|{n}': v for (o, n), v in rows}, fh, indent=1)
    # significant residential family changes (old R.* → new RL/RM/RH)
    sig = [(o, n, v) for (o, n), v in rows
           if (o or '').startswith('R.') and (n or '').startswith(('RL', 'RM', 'RH'))
           and family(o) != (family(n) or '').split('.')[0]]
    print(f'\nRESIDENTIAL FAMILY CHANGES: {len(sig)} pairs')
    for o, n, v in sorted(sig, key=lambda x: -x[2]['area'])[:20]:
        print(f'  {o:<12} -> {n:<10} polys={v["n"]:<6} area={v["area"]/1e6:.2f} km²')

def one_pager(street_no, street_name):
    """address lookup + old/new zone + parcel info; prints a one-pager"""
    where = f"STREETNO='{street_no}' and STREETNAME='{street_name.upper()}'"
    q = urllib.parse.urlencode({'where': where, 'outFields': 'ADDRESS,STREETNO,STREETNAME,PIN,LAT,LONG,ADDID',
                                'resultRecordCount': 10, 'f': 'json', 'outSR': 4326})
    adds = get(f'{ADDR}/query?{q}').get('features', [])
    if not adds:
        print(f'  {street_no} {street_name}: address not found'); return
    a = adds[0]['attributes']
    lat, lon = a['LAT'], a['LONG']
    oa = point_zone_attr(BASE_OLD, lat, lon, 'ZONE1')
    na = point_zone_attr(BASE_NEW, lat, lon, 'ZONING_CODE,ZONE_1')
    pa = point_zone_attr(PROP, lat, lon, 'PIN,GPID,OWNERSHIP,Shape__Area')
    old, new = (oa or {}).get('ZONE1'), (na or {}).get('ZONING_CODE')
    area = (pa or {}).get('Shape__Area')
    pin = (pa or {}).get('PIN') or a.get('PIN')
    print(f'\n=== ONE-PAGER: {a["ADDRESS"]} ===')
    print(f'  PIN: {pin}')
    print(f'  OLD (1995): {old}   NEW (2023): {new}   {"FAMILY CHANGE" if family(old)!=family(new) else "same family"}')
    if area: print(f'  Lot area: {area:,.0f} m² ({area/10000:.2f} ha)')
    if new and ('RM' in new or 'RL' in new or 'RH' in new):
        lo, hi = 0, 0
        if 'RM' in new: lo, hi = 35, 100
        if 'RL' in new: lo, hi = 20, 45
        if 'RH' in new: lo, hi = 100, 250
        if area:
            print(f'  Density {lo}-{hi} u/ha → rough potential: {area/10000*lo:.0f}-{area/10000*hi:.0f} units')
            print(f'  (existing units unknown — assess separately)')
    print(f'  Owner: {(pa or {}).get("OWNERSHIP") or "n/a"}')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--city', action='store_true', help='city-wide overlay')
    ap.add_argument('--addresses', nargs='*', default=[], help='e.g. --addresses "104 ELIZABETH ST" "10 GLENBROOK DR"')
    args = ap.parse_args()
    if args.city:
        city_overlay()
    for ad in args.addresses:
        parts = ad.split()
        if not parts: continue
        street_no = parts[0]
        street_name = ' '.join(parts[1:])
        one_pager(street_no, street_name)
