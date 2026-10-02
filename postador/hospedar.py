"""
hospedar.py — Publica as artes no GitHub Pages, de onde a Meta as baixa.

Por que não o imgbb: ele devolve dois endereços para a mesma imagem — o
original (1080x1350) e uma cópia reduzida (512x640) — e quatro posts foram ao
ar borrados porque a cópia entrou sem ninguém perceber.

O Pages serve o arquivo **byte por byte** como está no disco. Medido:
3 de 3 arquivos com SHA-256 idêntico ao local.

    ./.venv/bin/python hospedar.py            # envia as artes novas
    ./.venv/bin/python hospedar.py --conferir # confere se o servido bate
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

from .projeto import raiz
RAIZ = raiz()
IMAGENS = RAIZ / "posts" / "imagens"
REELS = RAIZ / "reels"
import marca   # do cliente

ESPELHO = Path("/tmp") / marca.REPO_MIDIA.split("/")[-1]
REPO = marca.REPO_MIDIA
BASE = marca.BASE_MIDIA


def _git(*args, cwd=ESPELHO, **kw):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=300, **kw)


def preparar():
    """Garante um clone local do repositório de mídia.

    No Mac usa o `gh`, que já está autenticado. No runner do GitHub o `gh`
    não serve: o token do workflow só vale no PRÓPRIO repositório, e o de
    mídia é outro. Por isso, se existir `MIDIA_TOKEN` no ambiente, clona
    por HTTPS com ele.

    O token NUNCA entra no `remote` gravado em disco — ia parar no
    `.git/config` do espelho, que fica em /tmp e sobrevive entre execuções.
    Ele é passado só no momento do comando.
    """
    import os
    token = os.getenv("MIDIA_TOKEN", "").strip()

    if (ESPELHO / ".git").exists():
        if token:
            _git("pull", "-q", "--rebase", _url(token), "HEAD")
        else:
            _git("pull", "-q", "--rebase")
        return

    ESPELHO.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(ESPELHO, ignore_errors=True)

    if token:
        r = subprocess.run(["git", "clone", "-q", _url(token), str(ESPELHO)],
                           capture_output=True, text=True, timeout=300)
    else:
        r = subprocess.run(["gh", "repo", "clone", REPO, str(ESPELHO)],
                           capture_output=True, text=True, timeout=300)
    if r.returncode:
        # o token apareceria inteiro na mensagem de erro do git
        erro = r.stderr[:200].replace(token, "***") if token else r.stderr[:200]
        raise SystemExit(f"não consegui clonar {REPO}: {erro}")


def _url(token: str) -> str:
    return f"https://x-access-token:{token}@github.com/{REPO}.git"


def empurrar():
    """Envia o espelho. Com MIDIA_TOKEN quando houver, pelo remoto quando não.

    Existe para que `enviar()` e `estado.publicar_estado()` empurrem do mesmo
    jeito — eram dois `_git("push")` soltos, e só um ia lembrar do token.
    """
    import os
    token = os.getenv("MIDIA_TOKEN", "").strip()
    r = _git("push", "-q", *( [_url(token), "HEAD"] if token else [] ))
    if r.returncode and token:
        r.stderr = r.stderr.replace(token, "***")
    return r


def _fontes():
    """Artes e reels. O reel fica na raiz de reels/, não em subpasta."""
    return sorted(IMAGENS.glob("*.jpg")) + sorted(REELS.glob("*.mp4"))


def enviar() -> int:
    preparar()
    novas = 0
    for img in _fontes():
        destino = ESPELHO / img.name
        if destino.exists() and destino.read_bytes() == img.read_bytes():
            continue
        # o Git recusa arquivo acima de 100 MB e reclama acima de 50 MB; e o
        # histórico guarda toda versão para sempre, então vídeo pesado aqui
        # incha o repositório de vez
        mb = img.stat().st_size / 1e6
        if mb > 95:
            print(f"  ⚠️ {img.name} tem {mb:.0f} MB — o GitHub recusa acima de 100")
            continue
        shutil.copy2(img, destino)
        novas += 1
        print(f"  + {img.name}  ({mb:.1f} MB)" if mb > 5 else f"  + {img.name}")

    if not novas:
        print("  Nada novo — o Pages já está em dia.")
        return 0

    _git("add", "-A")
    _git("-c", "user.name=Luiz Silva", "-c", "user.email=turbineseuscore991@gmail.com",
         "commit", "-q", "-m", f"artes: {novas} imagem(ns)")
    r = empurrar()
    if r.returncode:
        raise SystemExit(f"falhou ao enviar: {r.stderr[:200]}")
    print(f"\n✅ {novas} imagem(ns) no ar em {BASE}/")
    print("   O Pages leva ~1 minuto para publicar.")
    return novas


def conferir(quantas=3):
    """Compara o que o Pages serve com o arquivo do disco, byte por byte."""
    import requests
    from PIL import Image
    import io

    print(f"Conferindo o que {BASE} serve:\n")
    ok = falhas = 0
    for img in _fontes()[-quantas:]:
        try:
            b = requests.get(f"{BASE}/{img.name}", timeout=60).content
        except Exception as e:
            print(f"  ❌ {img.name}: {e}")
            falhas += 1
            continue
        local = img.read_bytes()
        igual = hashlib.sha256(b).hexdigest() == hashlib.sha256(local).hexdigest()
        try:
            larg, alt = Image.open(io.BytesIO(b)).size
        except Exception:
            larg = alt = 0      # vídeo: o SHA já diz tudo
        print(f'  {"✅" if igual else "❌"} {img.name:12} {larg}x{alt}  '
              f'{len(b)} bytes {"(idêntico)" if igual else "(ALTERADO)"}')
        ok += igual
        falhas += not igual
    print(f"\n{ok} idêntico(s), {falhas} com problema")
    return falhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conferir", action="store_true")
    a = ap.parse_args()
    if a.conferir:
        return 1 if conferir() else 0
    enviar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
