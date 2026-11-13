"""Relee la tienda (categorías y subcategorías) y compara contra el snapshot anterior.
Uso: python3 refresh.py [snapshot_anterior.json]
Escribe cat/crawl.json, cat/acc_subs.json, cat/rem_subs.json, cat/snapshot.json y cat/cambios.json."""
import json, os, sys, subprocess, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_list import parse

R = os.path.dirname(os.path.abspath(__file__))
os.makedirs(f'{R}/cat', exist_ok=True)
BASE = 'https://mummaindumentaria.com.ar'
CATS = ['remeras', 'camisas-blusas', 'sweaters-poleras', 'buzos', 'joggers-pantalones', 'blazers-chalecos',
        'shorts-polleras', 'vestidos', 'accesorios', 'valijas', 'liquidacion', 'primavera-verano', 'productos']
ACC = ['gorros', 'pashminas', 'carteras', 'cinturones', 'bijou', 'lentes', 'abanicos-lentes-y-complementos']
REM = ['lisas', 'estampadas', 'musculosas', 'bodys-tops']


def get(u):
    return subprocess.run(['curl', '-sSL', '--max-time', '40', '--retry', '2', u], capture_output=True, text=True).stdout


def crawl(path):
    items, seen, p = [], set(), 1
    while p < 200:
        new = [x for x in parse(get(f'{BASE}/{path}/page/{p}/')) if x['id'] not in seen]
        if not new: break
        seen |= {x['id'] for x in new}; items += new; p += 1
    return path, items


with cf.ThreadPoolExecutor(10) as ex:
    res = dict(ex.map(crawl, CATS + [f'accesorios/{s}' for s in ACC] + [f'remeras/{s}' for s in REM]))
crawl_json = {c: res[c] for c in CATS}
json.dump(crawl_json, open(f'{R}/cat/crawl.json', 'w'), ensure_ascii=False)
json.dump({s: res[f'accesorios/{s}'] for s in ACC}, open(f'{R}/cat/acc_subs.json', 'w'), ensure_ascii=False)
json.dump({s: [x['id'] for x in res[f'remeras/{s}']] for s in REM}, open(f'{R}/cat/rem_subs.json', 'w'))

# snapshot: id -> nombre, precio mínimo, precio tachado
snap = {}
for x in crawl_json['productos']:
    vs = x['variants'] or []
    snap[x['id']] = dict(name=x['name'], price=min((v['price_number'] for v in vs), default=0),
                         compare=max((v.get('compare_at_price_number') or 0 for v in vs), default=0))
json.dump(snap, open(f'{R}/cat/snapshot.json', 'w'), ensure_ascii=False)

prev = json.load(open(sys.argv[1])) if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
if prev is None:
    cambios = dict(primera_vez=True, total=len(snap))
else:
    entraron = [snap[i]['name'] for i in snap if i not in prev]
    salieron = [prev[i]['name'] for i in prev if i not in snap]
    precios = [f"{snap[i]['name']}: ${prev[i]['price']:,.0f} → ${snap[i]['price']:,.0f}".replace(',', '.')
               for i in snap if i in prev and (snap[i]['price'] != prev[i]['price'] or snap[i]['compare'] != prev[i]['compare'])]
    cambios = dict(primera_vez=False, total=len(snap), entraron=entraron, salieron=salieron, precios=precios,
                   hay_cambios=bool(entraron or salieron or precios))
# nuevos ingresos (15 días): ids de productos cargados desde la fecha de corte, según cat/id_por_fecha.json
# (la tarea guarda ahí el id más chico cargado cada día, tomado de Tiendanube)
json.dump(cambios, open(f'{R}/cat/cambios.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in cambios.items()}, ensure_ascii=False))
