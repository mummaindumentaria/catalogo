#!/bin/bash
# Prepara el entorno para generar el catálogo de Mumma (correr una vez por sesión, desde la carpeta del kit).
set -e
cd "$(dirname "$0")"
pip install --break-system-packages -q pillow pypdf 2>/dev/null || true
mkdir -p fonts
F=https://raw.githubusercontent.com/google/fonts/main/ofl
[ -f fonts/CormorantGaramond.ttf ] || curl -sSL -o fonts/CormorantGaramond.ttf "$F/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf"
[ -f fonts/CormorantGaramond-Italic.ttf ] || curl -sSL -o fonts/CormorantGaramond-Italic.ttf "$F/cormorantgaramond/CormorantGaramond-Italic%5Bwght%5D.ttf"
[ -f fonts/Jost.ttf ] || curl -sSL -o fonts/Jost.ttf "$F/jost/Jost%5Bwght%5D.ttf"
which google-chrome >/dev/null || { echo "FALTA google-chrome"; exit 1; }
echo "entorno listo"
