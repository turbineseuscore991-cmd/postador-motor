"""
aprovar.py — Leva as aprovações do painel para a fila real, num comando só.

O painel roda no navegador e guarda as decisões no localStorage — que some se
você limpar o histórico, e que o robô não enxerga. O robô lê `posts/aprovado.json`
no GitHub. Este script é a ponte entre os dois.

    1. No painel, clique em "⬇ Exportar aprovados"  (baixa para Downloads)
    2. ./.venv/bin/python aprovar.py

Ele acha o arquivo em Downloads, junta com o que já estava na fila, mostra o que
mudou e sobe para o GitHub. A partir daí as decisões estão seguras: nem limpar o
navegador as apaga.

    ./.venv/bin/python aprovar.py --ver     # só mostra a fila, não muda nada
"""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .projeto import raiz
RAIZ = raiz()
FILA = RAIZ / "posts" / "aprovado.json"
DOWNLOADS = Path.home() / "Downloads"


def carregar(caminho: Path) -> dict:
    if not caminho.exists():
        return {"posts": {}, "pedidos": []}
    d = json.loads(caminho.read_text(encoding="utf-8"))
    d.setdefault("posts", {})
    d.setdefault("pedidos", [])
    return d


def achar_export() -> Path | None:
    """O mais recente aprovado*.json em Downloads (o Chrome numera repetidos)."""
    achados = sorted(DOWNLOADS.glob("aprovado*.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    return achados[0] if achados else None


def nomes(plano_json: Path) -> dict:
    """id do post → 'POST 04 · sábado 01/08 às 11h'"""
    if not plano_json.exists():
        return {}
    fila = json.loads(plano_json.read_text(encoding="utf-8"))
    return {p["id"]: f'POST {i + 1:02d} · {p["dia_semana"]} {p["quando_br"]}'
            for i, p in enumerate(fila)}


def mostrar(fila: dict, rotulos: dict):
    posts = fila.get("posts", {})
    if not posts:
        print("  (fila vazia)")
        return
    for pid, v in sorted(posts.items(), key=lambda kv: rotulos.get(kv[0], kv[0])):
        marca = {"aprovado": "✅", "ajustar": "✏️"}.get(v.get("decisao"), "  ")
        print(f'  {marca} {rotulos.get(pid, pid)}')
    ok = sum(1 for v in posts.values() if v.get("decisao") == "aprovado")
    print(f'\n  {ok} aprovado(s) de {len(posts)} com decisão')
    if fila.get("pedidos"):
        print(f'\n  📋 {len(fila["pedidos"])} pedido(s) para eu executar:')
        for p in fila["pedidos"]:
            print(f'     · {p.get("descricao", p)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", action="store_true", help="só mostra a fila atual")
    ap.add_argument("--sem-push", action="store_true", help="não envia ao GitHub")
    a = ap.parse_args()

    rotulos = nomes(RAIZ / "posts" / "plano.json")
    atual = carregar(FILA)

    if a.ver:
        print(f"\n📋 Fila atual ({FILA.relative_to(RAIZ)}):\n")
        mostrar(atual, rotulos)
        return 0

    novo = achar_export()
    if not novo:
        print("❌ Não achei nenhum aprovado.json na pasta Downloads.\n")
        print("   No painel, clique em '⬇ Exportar aprovados' primeiro.")
        print(f"   Procurei em: {DOWNLOADS}")
        return 1

    idade = datetime.now() - datetime.fromtimestamp(novo.stat().st_mtime)
    print(f"\n📥 Achei: {novo.name}  (exportado há {int(idade.total_seconds()//60)} min)\n")

    chegando = carregar(novo)
    antes = dict(atual["posts"])

    atual["posts"].update(chegando["posts"])
    for p in chegando.get("pedidos", []):
        if p not in atual["pedidos"]:
            atual["pedidos"].append(p)
    atual["atualizado_em"] = datetime.now().isoformat()

    mudou = [pid for pid, v in chegando["posts"].items() if antes.get(pid) != v]
    if not mudou:
        print("  Nada novo — a fila já estava em dia.")
    else:
        print("  Mudanças:")
        for pid in mudou:
            d = chegando["posts"][pid].get("decisao")
            marca = {"aprovado": "✅", "ajustar": "✏️"}.get(d, "  ")
            print(f'    {marca} {rotulos.get(pid, pid)}')

    FILA.parent.mkdir(parents=True, exist_ok=True)
    FILA.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Gravado em {FILA.relative_to(RAIZ)}")

    # guarda o export usado, para não reprocessar sem querer
    usados = RAIZ / "posts" / "_exports"
    usados.mkdir(exist_ok=True)
    shutil.move(str(novo), usados / f'{datetime.now():%Y%m%d-%H%M}-{novo.name}')

    if a.sem_push:
        print("   (--sem-push: não enviei ao GitHub)")
        return 0

    try:
        subprocess.run(["git", "add", "posts/aprovado.json"], cwd=RAIZ, check=True,
                       capture_output=True, timeout=60)
        r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=RAIZ)
        if r.returncode == 0:
            print("   (nada mudou no arquivo — não precisou enviar)")
            return 0
        subprocess.run(["git", "commit", "-q", "-m",
                        f'aprovacoes: {datetime.now():%d/%m %H:%M}'],
                       cwd=RAIZ, check=True, capture_output=True, timeout=60)
        subprocess.run(["git", "push", "-q"], cwd=RAIZ, check=True,
                       capture_output=True, timeout=180)
        print("🚀 Enviado ao GitHub — o robô já enxerga.")
        print("   Suas decisões estão seguras: limpar o navegador não as apaga.")
    except subprocess.CalledProcessError as e:
        print(f'\n⚠️  Gravei aqui, mas o envio ao GitHub falhou:')
        print(f'   {(e.stderr or b"").decode()[:200]}')
        print('   Rode à mão: git add posts/ && git commit -m aprovados && git push')
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
