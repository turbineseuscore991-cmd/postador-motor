"""
plano.py — O calendário e as regras deste cliente.

`validar()` é o PORTÃO: roda antes de qualquer coisa ser renderizada ou ir ao
ar. Regra que não estiver aqui não é regra — é intenção.

    ./.venv/bin/python montar.py     # valida, renderiza, monta o painel, hospeda
"""
import unicodedata
from pathlib import Path

import marca

RAIZ = Path(__file__).resolve().parent
FOTOS = RAIZ / marca.PASTA_FOTOS

CARD = "__card__"   # post sem foto: só texto sobre um fundo
REEL = "__reel__"   # vídeo produzido à parte

NOME_OFICIAL = marca.NOME_OFICIAL

# As faixas em que o robô acorda. ESPELHA o cron de
# .github/workflows/publicar.yml — mudou uma, mude a outra, senão o post é
# aceito na validação e some sem publicar.
JANELAS = [(6, 9), (11, 13), (17, 20)]


def hora_valida(h: int) -> bool:
    return any(ini <= h <= fim for ini, fim in JANELAS)


def achar_foto(trecho: str) -> str:
    """Casa a foto por um trecho do nome, ignorando acento e caixa."""
    def normal(s):
        return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                       if unicodedata.category(c) != "Mn")
    alvo = normal(trecho)
    achados = [p for p in FOTOS.iterdir()
               if p.suffix.lower() in (".jpeg", ".jpg", ".png")
               and alvo in normal(p.name)]
    if len(achados) != 1:
        raise SystemExit(f"'{trecho}' casou com {len(achados)} arquivos: "
                         + ", ".join(p.name for p in achados))
    return achados[0].name


# Fundo de cada card, por id do post. Tema vem de postador/bancos.py (Pexels).
# Cada imagem entra UMA vez — a validação recusa fundo repetido.
FUNDOS = {
    # "p01": "ceu",
}

PLANO = [
    {
        "id": "p01",
        "quando": "2026-01-01 08:00",       # AAAA-MM-DD HH:MM
        "tipo": "foto",                     # foto · card · carrossel · reel
        "foto": achar_foto("parte-do-nome-do-arquivo"),
        "titulo": "Título da Arte",
        "lower": ["Linha de baixo", "Segunda linha"],
        "corpo": "O texto do post, no máximo 200 caracteres.",
        # versículo é OPCIONAL. Sem ele, a legenda é corpo + hashtags.
        # "versiculo": ["Salmos 1:1", "Bem-aventurado o homem…"],
        # ou uma citação da fonte do próprio cliente, que sai com 📜:
        # "citacao": ["Fonte", "texto"],
        "tags": "#uma #duas #tres #quatro #cinco",
    },
]


def legenda(post: dict) -> str:
    """Corpo + versículo/citação (se houver) + hashtags."""
    partes = [post["corpo"]]
    if post.get("versiculo"):
        ref, texto = post["versiculo"]
        partes.append(f'📖 {ref} — "{texto}"')
    elif post.get("citacao"):
        fonte, texto = post["citacao"]
        partes.append(f'📜 {fonte} — "{texto}"')
    partes.append(post["tags"])
    return "\n\n".join(partes)


def _JA_PUBLICADOS() -> set:
    """Post que já foi ao ar não pode mais ser corrigido — não adianta acusar."""
    import json
    arq = RAIZ / "posts" / "publicados.json"
    if not arq.exists():
        return set()
    try:
        return set(json.loads(arq.read_text(encoding="utf-8")))
    except Exception:
        return set()


def validar():
    """As regras invioláveis deste cliente. Devolve a lista de erros."""
    erros, vistos, fotos = [], set(), {}
    faixas = " · ".join(f"{i}h–{f}h" for i, f in JANELAS)

    for p in PLANO:
        pid, c = p["id"], p["corpo"]

        if len(c) > 200:
            erros.append(f'{pid}: corpo com {len(c)} caracteres (máx. 200)')
        if len(p["tags"].split()) != 5:
            erros.append(f'{pid}: {len(p["tags"].split())} hashtags (devem ser 5)')
        emojis = sum(1 for ch in c if ord(ch) > 0x2100)
        if emojis > 2:
            erros.append(f'{pid}: {emojis} emojis no corpo (máx. 2)')

        # horário fora das faixas = post que some calado, sem publicar
        h = int(p["quando"][11:13])
        if not hora_valida(h) and pid not in _JA_PUBLICADOS():
            erros.append(f'{pid}: marcado para {h}h, fora das faixas em que o '
                         f'robô acorda ({faixas}) — ele não sairia')

        # versículo não se repete
        if p.get("versiculo"):
            ref = p["versiculo"][0]
            if ref in vistos:
                erros.append(f'{pid}: versículo {ref} repetido')
            vistos.add(ref)

        # a mesma foto não entra duas vezes
        if p.get("foto") not in (None, CARD, REEL):
            if p["foto"] in fotos:
                erros.append(f'{pid}: mesma foto de {fotos[p["foto"]]}')
            fotos[p["foto"]] = pid

    # ------------------------------------------------------------------
    # AQUI entram as regras próprias deste cliente. Exemplos do Arco Real:
    #   · termo proibido:  if "Santo Arco Real" in c: erros.append(…)
    #   · saudação tem de bater com a hora ("Bom dia" só antes do meio-dia)
    #   · título não pode repetir nem chegar perto de outro recente
    # ------------------------------------------------------------------

    return erros


if __name__ == "__main__":
    e = validar()
    print("\n".join(e) if e else f"✅ {len(PLANO)} posts, plano válido")
