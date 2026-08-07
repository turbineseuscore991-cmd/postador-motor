"""
bancos.py — Baixa fundos reais para os cards de versículo.

Duas fontes, nessa ordem:

  1. PEXELS — biblioteca enorme, alta resolução, uso comercial livre e sem
     exigir crédito. Precisa de uma chave grátis (sem cartão) em
     https://www.pexels.com/api/ → põe PEXELS_API_KEY no .env.

  2. OPENVERSE — funciona SEM chave nenhuma, mas o acervo é bem menor e a
     resolução costuma ser menor. Serve de quebra-galho.

    ./.venv/bin/python bancos.py --listar          # mostra os temas
    ./.venv/bin/python bancos.py                   # baixa todos
    ./.venv/bin/python bancos.py --tema aguia -n 5 # só um tema
"""
import argparse
import os
import sys
from pathlib import Path

import requests

from .projeto import raiz
RAIZ = raiz()
DESTINO = RAIZ / "assets" / "fundos"

try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

# Temas pensados para o tom do Arco Real: solene, luz vinda de cima, natureza
# grandiosa. Nada de gente, nada de moderno.
TEMAS = {
    "ceu":        "dramatic sky sunbeams golden clouds",
    "nuvens":     "storm clouds light rays heaven",
    "aguia":      "eagle flying majestic sky",
    "cachoeira":  "waterfall mist forest cinematic",
    "deserto":    "desert dunes golden hour israel",
    "montanha":   "mountain peak sunrise mist",
    "oceano":     "ocean waves aerial drone blue",
    "mar_calmo":  "calm sea horizon sunrise minimal",
    "barco":      "lone boat aerial ocean top view",
    "floresta":   "forest sunbeams fog ancient trees",
    "leao":       "lion portrait golden light savanna",
    "pedra":      "ancient stone temple ruins jerusalem",
    "trigo":      "wheat field golden sunset wind",
    "estrelas":   "night sky stars milky way desert",

    # --- imagens que falam sozinhas: união, jornada, trabalho, esperança ---
    "maos_unidas":  "hands together unity circle silhouette sunset",
    "multidao":     "crowd people together unity gathering silhouette",
    "caminho":      "long path through mountains journey solitary",
    "horizonte":    "person standing on cliff looking at vast horizon",
    "ponte":        "ancient stone bridge fog river",
    "porta_antiga": "ancient wooden door stone arch weathered",
    "vela":         "single candle flame in darkness warm glow",
    "fogo":         "bonfire sparks night embers rising",
    "tempestade":   "lightning storm dramatic clouds power",
    "neblina":      "fog forest mystical morning light rays",
    "vale":         "vast green valley mountains aerial landscape",
    "ruinas":       "ancient stone ruins columns temple weathered",
    "livro":        "old open book candlelight parchment study",
    "corrente":     "iron chain links close up strength",
    "bigorna":      "blacksmith hammer anvil sparks forge",
    "semente":      "seedling sprouting soil sunlight hope",
    "aguia_voo":    "eagle soaring above clouds mountains wings",
    "aguia_olhar":  "eagle head close up eye intense portrait",
    "escadaria":    "ancient stone staircase ascending light",
    "coluna":       "ancient stone column low angle sky",
}


def _pexels(consulta, n):
    chave = os.getenv("PEXELS_API_KEY", "").strip()
    if not chave:
        return None
    r = requests.get("https://api.pexels.com/v1/search",
                     headers={"Authorization": chave},
                     params={"query": consulta, "per_page": n,
                             "orientation": "portrait", "size": "large"},
                     timeout=40)
    if r.status_code == 401:
        raise SystemExit("PEXELS_API_KEY inválida.")
    r.raise_for_status()
    return [(f['id'], f["src"]["original"]) for f in r.json().get("photos", [])]


def _openverse(consulta, n):
    r = requests.get("https://api.openverse.org/v1/images/",
                     params={"q": consulta, "license_type": "commercial",
                             "size": "large", "page_size": n},
                     headers={"User-Agent": "arcoreal-bot/1.0"}, timeout=40)
    r.raise_for_status()
    return [(i["id"][:8], i["url"]) for i in r.json().get("results", [])]


def baixar(tema, consulta, n):
    pasta = DESTINO / tema
    pasta.mkdir(parents=True, exist_ok=True)

    achados = _pexels(consulta, n)
    fonte = "pexels"
    if achados is None:
        achados = _openverse(consulta, n)
        fonte = "openverse"
    if not achados:
        print(f"  ⚠️  {tema}: nada encontrado")
        return 0

    salvos = 0
    for ident, url in achados:
        destino = pasta / f"{fonte}_{ident}.jpg"
        if destino.exists():
            salvos += 1
            continue
        try:
            img = requests.get(url, timeout=90,
                               headers={"User-Agent": "arcoreal-bot/1.0"})
            img.raise_for_status()
            destino.write_bytes(img.content)
            salvos += 1
        except Exception as e:
            print(f"  ⚠️  {tema}/{ident}: {e}")
    return salvos


MANUAL = RAIZ / "IMAGENS POST"
EXTS = (".jpg", ".jpeg", ".png", ".webp")


def escolher(tema):
    """Aceita duas formas:
        "portal-dourado.jpg"  → arquivo escolhido a dedo em IMAGENS POST/
        "ceu"                 → tema baixado em assets/fundos/

    Devolve None se não achar — o render cai no degradê da marca e nunca quebra.
    """
    if not tema:
        return None

    # arquivo específico tem prioridade sobre tema automático
    if tema.lower().endswith(EXTS):
        alvo = MANUAL / tema
        return alvo if alvo.exists() else None
    manual = MANUAL / tema
    if manual.exists() and manual.is_file():
        return manual

    pasta = DESTINO / tema
    if not pasta.exists():
        return None
    fotos = sorted(p for p in pasta.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    return fotos[0] if fotos else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tema", help="baixar só um tema")
    ap.add_argument("-n", type=int, default=3, help="quantas por tema")
    ap.add_argument("--listar", action="store_true")
    args = ap.parse_args()

    if args.listar:
        for t, q in TEMAS.items():
            atual = escolher(t)
            print(f'  {t:11} {q:45} {"✓ " + atual.name if atual else "—"}')
        return

    if not os.getenv("PEXELS_API_KEY", "").strip():
        print("ℹ️  Sem PEXELS_API_KEY — usando Openverse (acervo menor).")
        print("   Chave grátis e sem cartão: https://www.pexels.com/api/\n")

    temas = {args.tema: TEMAS[args.tema]} if args.tema else TEMAS
    total = 0
    for t, q in temas.items():
        n = baixar(t, q, args.n)
        total += n
        print(f"  {t:11} {n} imagem(ns)")
    print(f"\n✅ {total} fundos em assets/fundos/")


if __name__ == "__main__":
    sys.exit(main())
