"""Corrida diaria en GitHub Actions: lee la tienda, detecta cambios y, si hubo, regenera el PDF del link público.

Uso: python3 kit/ci.py [--forzar]
Deja en GITHUB_OUTPUT: cambio=true|false y resumen=<texto>.
"""
import datetime, json, os, shutil, subprocess, sys

K = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(K)
CAT = f'{K}/cat'
HOY = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).date()  # hora de Buenos Aires
DIAS_NUEVO = 15
forzar = '--forzar' in sys.argv


def run(*cmd, env=None):
    print('$', ' '.join(cmd), flush=True)
    subprocess.run(cmd, cwd=K, check=True, env={**os.environ, **(env or {})})


def salida(clave, valor):
    f = os.environ.get('GITHUB_OUTPUT')
    if f:
        with open(f, 'a') as fh: fh.write(f'{clave}={valor}\n')
    print(f'{clave}={valor}')


# 1) leer la tienda y comparar contra la corrida anterior
shutil.copy(f'{CAT}/snapshot.json', f'{K}/prev_snapshot.json')
run('python3', '-I', 'refresh.py', 'prev_snapshot.json')
cambios = json.load(open(f'{CAT}/cambios.json'))
if cambios['total'] < 300:
    sys.exit(f"La lectura de la tienda devolvió solo {cambios['total']} productos: algo falló, no se actualiza el link.")

# 2) nuevos ingresos: fecha en que cada producto apareció por primera vez en la tienda
first = json.load(open(f'{CAT}/first_seen.json'))
snap = json.load(open(f'{CAT}/snapshot.json'))
for pid in snap:
    first.setdefault(pid, HOY.isoformat())
first = {k: v for k, v in first.items() if k in snap}
limite = (HOY - datetime.timedelta(days=DIAS_NUEVO)).isoformat()
nuevos = sorted([k for k, v in first.items() if v >= limite], key=lambda i: -int(i))
json.dump(nuevos, open(f'{CAT}/new_ids.json', 'w'))

hay = cambios.get('hay_cambios') or forzar
if not hay:
    # sin cambios: se descarta la lectura de hoy para no tocar el repositorio
    subprocess.run(['git', 'checkout', '--', 'kit/cat/snapshot.json'], cwd=REPO)
    salida('cambio', 'false')
    sys.exit(0)

json.dump(first, open(f'{CAT}/first_seen.json', 'w'), indent=0, sort_keys=True)

# 3) generar la versión liviana y controlarla
run('python3', '-I', 'build_all.py', 'Completo', env={'MUMMA_LIVIANO': '1'})
pdf = f'{K}/out/catalogos/Mumma - Catalogo Completo (liviano).pdf'
from pypdf import PdfReader
r = PdfReader(pdf)
paginas, mb = len(r.pages), os.path.getsize(pdf) / 1e6
indice = 'ÍNDICE' in (r.pages[1].extract_text() or '').upper()
print(f'PDF: {paginas} páginas, {mb:.1f} MB, índice ok: {indice}')
if paginas < 150 or mb > 45 or not indice:
    sys.exit('El PDF no pasó el control: no se actualiza el link.')
shutil.copy(pdf, f'{REPO}/catalogo-mumma.pdf')

entraron, salieron = len(cambios.get('entraron', [])), len(cambios.get('salieron', []))
salida('cambio', 'true')
salida('resumen', f'Catálogo al {HOY.strftime("%d/%m/%Y")}: {paginas} págs, entraron {entraron}, se agotaron {salieron}')
