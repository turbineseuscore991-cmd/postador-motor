"""
historico.py — Memória permanente do que já foi ao ar.

A validação do `plano.py` só enxerga o mês corrente. Este arquivo é a memória
longa: guarda todo versículo, foto, fundo e legenda já publicados, para que
nada se repita mês que vem, nem no ano que vem.

Registrado automaticamente pelo `publicar.py` no momento em que o post sai.
Consultado pelo `plano.validar()` antes de qualquer coisa ser renderizada.

    ./.venv/bin/python historico.py            # o que já foi usado
    ./.venv/bin/python historico.py --checar    # o plano atual repete algo?
"""
import hashlib
import json
import re
from pathlib import Path

from .projeto import raiz
RAIZ = raiz()
ARQUIVO = RAIZ / "posts" / "historico.json"

VAZIO = {"versiculos": {}, "fotos": {}, "fundos": {}, "legendas": {}}


def carregar() -> dict:
    if not ARQUIVO.exists():
        return json.loads(json.dumps(VAZIO))
    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    for chave in VAZIO:
        dados.setdefault(chave, {})
    return dados


def salvar(dados: dict) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                       encoding="utf-8")


def impressao(texto: str) -> str:
    """Identidade da legenda: minúsculas, sem pontuação, sem hashtag. Pega
    reescrita disfarçada, não só cópia literal."""
    limpo = re.sub(r"#\w+", "", texto.lower())
    limpo = re.sub(r"[^a-zà-ú0-9 ]", " ", limpo)
    return hashlib.sha1(" ".join(limpo.split()).encode()).hexdigest()[:16]


def registrar(post: dict, legenda: str, quando: str) -> None:
    """Chamado quando o post realmente foi publicado."""
    d = carregar()
    pid = post.get("id", "?")
    marca = f"{pid} · {quando}"

    ref = (post.get("versiculo") or [None])[0]
    if ref:
        d["versiculos"].setdefault(ref, marca)
    foto = post.get("foto", "")
    if foto and not foto.startswith("__"):
        d["fotos"].setdefault(foto, marca)
    for slide in post.get("carrossel", []) or []:
        f = slide.get("foto", "") if isinstance(slide, dict) else slide
        if f and not f.startswith("__"):
            d["fotos"].setdefault(f, marca)
    if post.get("fundo"):
        d["fundos"].setdefault(post["fundo"], marca)
    d["legendas"].setdefault(impressao(legenda), marca)

    salvar(d)


def conferir(plano_posts, legenda_de) -> list:
    """Devolve os choques entre o plano proposto e o que já foi publicado.

    Um post não colide consigo mesmo: depois de publicado, ele continua no
    plano e o seu próprio registro no histórico não deve acusá-lo.
    """
    d = carregar()
    choques = []

    def alheio(marca, pid):
        return not str(marca).startswith(f"{pid} ")

    for p in plano_posts:
        pid = p["id"]
        ref = (p.get("versiculo") or [None])[0]
        if ref and ref in d["versiculos"] and alheio(d["versiculos"][ref], pid):
            choques.append(f'{pid}: versículo {ref} já usado em {d["versiculos"][ref]}')
        foto = p.get("foto", "")
        if (foto and not foto.startswith("__") and foto in d["fotos"]
                and alheio(d["fotos"][foto], pid)):
            choques.append(f'{pid}: foto já usada em {d["fotos"][foto]}')
        h = impressao(legenda_de(p))
        if h in d["legendas"] and alheio(d["legendas"][h], pid):
            choques.append(f'{pid}: legenda equivalente já usada em {d["legendas"][h]}')
    return choques


def resumo() -> str:
    d = carregar()
    return (f'{len(d["versiculos"])} versículos · {len(d["fotos"])} fotos · '
            f'{len(d["fundos"])} fundos · {len(d["legendas"])} legendas')


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--checar", action="store_true")
    a = ap.parse_args()

    if a.checar:
        import plano
        problemas = conferir(plano.PLANO, plano.legenda)
        if problemas:
            print("⚠️  O plano atual repete coisa já publicada:")
            for p in problemas:
                print("  •", p)
        else:
            print("✅ Nada no plano atual se repete.")
    else:
        d = carregar()
        print("Já publicado —", resumo(), "\n")
        for secao in ("versiculos", "fotos", "fundos"):
            if d[secao]:
                print(f"{secao.upper()}:")
                for k, v in list(d[secao].items())[:40]:
                    print(f"  {k[:66]:68} {v}")
                print()
