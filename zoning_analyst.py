#!/data/.gvenv/bin/python
"""Zoning Analyst engine (v0) — old-vs-new zoning overlay test on one street.
Read-only against Guelph Open Data (gismaps.guelph.ca ArcGIS REST).
Test brief: per-parcel old (1995-14864) vs new (Zoning 2023-20790) zone comparison.
Pass: >=90% of parcels resolve in both layers AND 64 Cedar returns RM.5 in the new layer.
"""
import json, sys, time, argparse
import urllib.request, urllib.parse

BASE_OLD = 'https://gismaps.guelph.ca/hosting/rest/services/OpenData/OpenData1/FeatureServer/9'
BASE_NEW = 'https://gismaps.guelph.ca/hosting/rest/services/OpenData/OpenData2/FeatureServer/16'
ADDR     = 'https://gismaps.guelph.ca/hosting/rest/services/OpenData/OpenData1/FeatureServer/0'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def query(layer_url, where, out_fields, limit=2000):
    q = urllib.parse.urlencode({'where': where, 'outFields': out_fields,
                                'resultRecordCount': limit, 'f': 'json',
                                'outSR': 4326})
    d = get(f'{layer_url}/query?{q}')
    return d.get('features', [])

def point_zone(layer_url, lat, lon, field):
    """zone code at a point; returns (code, found)"""
    q = urllib.parse.urlencode({'geometry': f'{lon},{lat}', 'geometryType': 'esriGeometryPoint',
                                'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects',
                                'outFields': field, 'f': 'json', 'outSR': 4326})
    try:
        d = get(f'{layer_url}/query?{q}')
        fs = d.get('features', [])
        if fs:
            return fs[0]['attributes'].get(field), True
        return None, False
    except Exception:
        return None, False

def main(street, test_address=None, expect_zone=None):
    print(f'STREET={street}')
    # 1. addresses on the street
    where = f"STREETNAME='{street.upper()}' and STATUS='ACTIVE'"
    adds = query(ADDR, where, 'ADDRESS,STREETNO,STREETNAME,PIN,LAT,LONG,UNIT_NO,ROLL_NO')
    print(f'ADDRESSES={len(adds)}')
    if not adds:
        print('NO ADDRESSES FOUND'); return
    rows, matched, unmapped = [], 0, []
    for a in adds:
        at = a['attributes']
        lat, lon = at.get('LAT'), at.get('LONG')
        if lat is None or lon is None:
            unmapped.append((at['ADDRESS'], 'no coords')); continue
        old, ok1 = point_zone(BASE_OLD, lat, lon, 'ZONE1')
        new, ok2 = point_zone(BASE_NEW, lat, lon, 'ZONING_CODE')
        rows.append({'address': at.get('ADDRESS'), 'no': at.get('STREETNO'),
                     'pin': at.get('PIN'), 'old': old, 'new': new, 'ok1': ok1, 'ok2': ok2})
        if ok1 and ok2: matched += 1
        else: unmapped.append((at.get('ADDRESS'), f'old={old} new={new}'))
        time.sleep(0.12)
    both = len(rows)
    rate = matched / both * 100 if both else 0
    changed = [r for r in rows if r['ok1'] and r['ok2'] and r['old'] != r['new']]
    print(f'RESOLVED_BOTH={matched}/{both} ({rate:.1f}%)')
    print(f'CHANGED_ZONES={len(changed)}')
    print('\nADDRESS | OLD(1995) -> NEW(2023) | PIN')
    for r in sorted(rows, key=lambda x: (x['no'] or 0)):
        mark = ' *CHANGED*' if (r['ok1'] and r['ok2'] and r['old'] != r['new']) else ''
        print(f"  {r['address']:<28} {r['old'] or '?':<12} -> {r['new'] or '?':<12} {r['pin'] or ''}{mark}")
    if unmapped:
        print('\nUNMAPPED:')
        for u in unmapped: print('  ', u)
    if test_address:
        hit = [r for r in rows if (r['address'] or '').strip().lower().startswith(str(test_address).lower().split()[0]) and (r['no'] or 0) == int(test_address.split()[0])]
        hit = [r for r in rows if str(r['no']) == str(test_address.split()[0])]
        if hit:
            r = hit[0]
            verdict = 'PASS' if expect_zone and r['new'] == expect_zone else 'FAIL'
            print(f"\nTEST {test_address}: NEW zone = {r['new']} (expected {expect_zone}) -> {verdict}")
        else:
            print(f"\nTEST {test_address}: not found in address list")
    total_ok = rate >= 90.0
    print(f"\nPASS_CONDITION: resolution >=90% -> {'PASS' if total_ok else 'FAIL'} ({rate:.1f}%)")

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--street', default='CEDAR')
    ap.add_argument('--test', default='64 CEDAR', help='address + expected zone, e.g. "64 RM.5" or "—"')
    args = ap.parse_args()
    exp = None
    if args.test and args.test.lower() not in ('-', 'none'):
        parts = args.test.split()
        addr = parts[0]
        exp = ' '.join(parts[1:]) or None
        main(args.street, test_address=addr, expect_zone=exp)
    else:
        main(args.street)
