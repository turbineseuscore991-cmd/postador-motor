"""
saude.py — Confere de manhã se o sistema vai conseguir postar hoje.

Existe por uma falha real: em 29/07 o token da Meta foi invalidado durante o dia
e o post das 17h simplesmente não saiu. O erro só apareceu na hora — tarde.

Este script roda cedo, testa tudo ANTES de qualquer post vencer e avisa no
Telegram se algo estiver quebrado. Assim dá tempo de consertar.

    ./.venv/bin/python saude.py            # confere e avisa se houver problema
    ./.venv/bin/python saude.py --sempre   # avisa mesmo quando está tudo bem
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from .projeto import raiz
RAIZ = raiz()
sys.path.insert(0, str(RAIZ))

try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

BRT = timezone(timedelta(hours=-3))


def avisar(texto):
    tok = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not (tok and chat):
        return
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      data={"chat_id": chat, "text": texto, "parse_mode": "HTML",
                            "disable_web_page_preview": "true"}, timeout=20)
    except Exception:
        pass


def conferir() -> tuple[list, list]:
    """Devolve (problemas, informações)."""
    problemas, infos = [], []

    # 1) A Meta responde e o token publica?
    try:
        from . import meta_api
        pagina = meta_api._chamar("GET", os.getenv("FB_PAGE_ID", ""), fields="name")
        conta = meta_api._chamar("GET", os.getenv("IG_USER_ID", ""),
                                 fields="username,media_count")
        infos.append(f'✅ Meta ligada — @{conta.get("username")} '
                     f'({conta.get("media_count")} posts) e {pagina.get("name")[:30]}')
    except Exception as e:
        problemas.append(f'❌ <b>Meta fora do ar</b>\n<code>{str(e)[:180]}</code>')

    # 2) A hospedagem de imagem funciona?
    if os.getenv("IMGBB_API_KEY", "").strip() or os.getenv("MIDIA_BASE_URL", "").strip():
        infos.append("✅ Hospedagem de imagem configurada")
    else:
        problemas.append("❌ Sem IMGBB_API_KEY nem MIDIA_BASE_URL — a foto não sobe")

    # 3) Há post aprovado para as próximas 24h?
    plano = RAIZ / "posts" / "plano.json"
    aprov = RAIZ / "posts" / "aprovado.json"
    feitos = RAIZ / "posts" / "publicados.json"
    if plano.exists():
        fila = json.loads(plano.read_text(encoding="utf-8"))
        decisoes = (json.loads(aprov.read_text(encoding="utf-8")).get("posts", {})
                    if aprov.exists() else {})
        ja = (json.loads(feitos.read_text(encoding="utf-8")) if feitos.exists() else {})
        agora = datetime.now(BRT)
        limite = agora + timedelta(hours=26)

        proximos = []
        for p in fila:
            q = datetime.strptime(p["quando"], "%Y-%m-%d %H:%M").replace(tzinfo=BRT)
            if p["id"] in ja or not (agora <= q <= limite):
                continue
            ok = decisoes.get(p["id"], {}).get("decisao") == "aprovado"
            proximos.append((p, q, ok))

        if not proximos:
            infos.append("ℹ️ Nenhum post marcado para as próximas 24h")
        for p, q, ok in proximos:
            if ok:
                infos.append(f'✅ {q:%d/%m %Hh} — {p["tipo"]} pronto para sair')
            else:
                problemas.append(f'⚠️ {q:%d/%m %Hh} — <b>post não aprovado</b>, '
                                 f'não vai sair ({p["id"]})')
            # NADA sai se o arquivo não estiver NO AR — a Meta não recebe
            # upload, ela BAIXA do endereço público. Conferir aqui, um dia
            # antes, é o que dá tempo de rodar `hospedar.py`; descobrir na hora
            # já é tarde. Custou o reel de 03/08 (saiu 10h em vez de 7h) e o
            # post de 06/08, que morreu com "9004 Only photo or video".
            from . import publicar
            alvos = [p["imagem"]] if p.get("imagem") else []
            if p["tipo"] == "reel":
                if not p.get("video"):
                    problemas.append(f'⚠️ {q:%d/%m %Hh} — reel sem vídeo no plano')
                else:
                    alvos.append(p["video"])
            for alvo in alvos:
                url = publicar.primeiro(publicar.url_publica(RAIZ / alvo))
                if not publicar.video_no_ar(url):
                    problemas.append(
                        f'⚠️ {q:%d/%m %Hh} — <b>{Path(alvo).name} não está no '
                        f'ar</b>. Rode <code>python hospedar.py</code> '
                        f'({p["id"]})')

    return problemas, infos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sempre", action="store_true",
                    help="manda no Telegram mesmo se estiver tudo bem")
    a = ap.parse_args()

    problemas, infos = conferir()
    agora = datetime.now(BRT)

    print(f'Checagem de {agora:%d/%m/%Y %H:%M}\n')
    for i in infos:
        print("  " + i)
    for p in problemas:
        print("  " + p.replace("<b>", "").replace("</b>", "")
                     .replace("<code>", "").replace("</code>", ""))

    if problemas:
        avisar("🔧 <b>Arco Real — atenção</b>\n\n" + "\n\n".join(problemas)
               + "\n\n<i>Corrija antes do próximo horário de post.</i>")
        print("\n📲 Avisei no Telegram.")
        return 1
    if a.sempre:
        avisar("✅ <b>Arco Real — tudo em ordem</b>\n\n" + "\n".join(infos))
        print("\n📲 Avisei no Telegram.")
    else:
        print("\n✅ Nada a reportar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
