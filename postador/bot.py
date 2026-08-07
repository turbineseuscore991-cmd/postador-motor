"""
bot.py — Faz o @arcorealbot responder perguntas, não só avisar.

Até agora o bot só mandava mensagem. Agora você pode perguntar:

    status          → o que já saiu, o que vem, se o token está de pé
    proximo         → o próximo post com a legenda inteira
    fila            → o que está aprovado esperando
    saude           → checagem completa (token, hospedagem, aprovações)
    ajuda           → esta lista

Escreva em português normal — "como está o status?", "qual o próximo post?",
"tá tudo ok?" funcionam igual.

Onde ele escuta:
    · no robô do GitHub, a cada hora → responde mesmo com o Mac desligado
    · localmente, se você rodar `bot.py --escutar` → responde em segundos

    ./.venv/bin/python bot.py            # responde o que chegou e sai
    ./.venv/bin/python bot.py --escutar  # fica escutando (Ctrl+C para parar)
"""
import argparse
import json
import os
import sys
import time
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
POSTS = RAIZ / "posts"
MARCA = POSTS / ".bot_offset"          # último recado já respondido


def _api(metodo, _timeout_http=40, **params):
    tok = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not tok:
        raise SystemExit("TELEGRAM_BOT_TOKEN não definido")
    try:
        r = requests.post(f"https://api.telegram.org/bot{tok}/{metodo}",
                          data=params, timeout=_timeout_http)
        return r.json()
    except requests.exceptions.Timeout:
        return {"ok": False, "result": []}


def responder(texto, chat=None):
    _api("sendMessage", chat_id=chat or os.getenv("TELEGRAM_CHAT_ID", ""),
         text=texto, parse_mode="HTML", disable_web_page_preview="true")


# ---------------------------------------------------------------------------
# As respostas
# ---------------------------------------------------------------------------

def _ler(nome, padrao):
    p = POSTS / nome
    if not p.exists():
        return padrao
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return padrao


def _fila():
    plano = _ler("plano.json", [])
    aprov = _ler("aprovado.json", {}).get("posts", {})
    feitos = _ler("publicados.json", {})
    agora = datetime.now(BRT)
    saida = []
    for i, p in enumerate(plano, 1):
        q = datetime.strptime(p["quando"], "%Y-%m-%d %H:%M").replace(tzinfo=BRT)
        saida.append({
            "n": i, "id": p["id"], "tipo": p["tipo"], "quando": q,
            "publicado": p["id"] in feitos,
            "aprovado": aprov.get(p["id"], {}).get("decisao") == "aprovado",
            "legenda": aprov.get(p["id"], {}).get("legenda") or p["legenda"],
            "futuro": q > agora,
        })
    return saida


def resp_status():
    f = _fila()
    pub = [x for x in f if x["publicado"]]
    prox = [x for x in f if x["futuro"] and not x["publicado"]]
    falhas = _ler("falhas.json", {})

    linhas = ["📊 <b>Arco Real — status</b>", ""]
    linhas.append(f'✅ {len(pub)} já publicados')
    linhas.append(f'📅 {len(prox)} programados')
    aprovados = sum(1 for x in prox if x["aprovado"])
    linhas.append(f'👍 {aprovados} deles aprovados e prontos')
    se_falta = len(prox) - aprovados
    if se_falta:
        linhas.append(f'⚠️ {se_falta} <b>sem aprovação</b> — não vão sair')

    if prox:
        p = prox[0]
        marca = "✅" if p["aprovado"] else "⚠️ falta aprovar"
        linhas += ["", f'<b>Próximo:</b> POST {p["n"]:02d} · {p["tipo"]}',
                   f'{p["quando"]:%d/%m às %Hh} — {marca}']

    if falhas:
        linhas += ["", "🛑 <b>Com problema:</b>"]
        for pid, v in falhas.items():
            linhas.append(f'{pid}: {v["vezes"]}x — {v["erro"][:70]}')

    try:
        from . import meta_api
        c = meta_api._chamar("GET", os.getenv("IG_USER_ID", ""),
                             fields="username,media_count,followers_count")
        linhas += ["", f'🔗 @{c["username"]} — {c["followers_count"]} seguidores, '
                       f'{c["media_count"]} posts']
    except Exception as e:
        linhas += ["", f'❌ <b>Meta fora:</b> {str(e)[:110]}']

    return "\n".join(linhas)


def resp_proximo():
    prox = [x for x in _fila() if x["futuro"] and not x["publicado"]]
    if not prox:
        return "Nenhum post programado à frente. Me avise que eu monto mais."
    p = prox[0]
    marca = ("✅ aprovado, vai sair sozinho" if p["aprovado"]
             else "⚠️ ainda NÃO aprovado — abra o painel")
    return (f'📅 <b>POST {p["n"]:02d}</b> · {p["tipo"]}\n'
            f'{p["quando"]:%A, %d/%m às %Hh}\n{marca}\n\n'
            f'<i>{p["legenda"][:600]}</i>')


def resp_fila():
    prox = [x for x in _fila() if x["futuro"] and not x["publicado"]][:10]
    if not prox:
        return "Fila vazia."
    linhas = ["📋 <b>Próximos posts</b>", ""]
    for p in prox:
        linhas.append(f'{"✅" if p["aprovado"] else "⬜"} POST {p["n"]:02d} · '
                      f'{p["quando"]:%d/%m %Hh} · {p["tipo"]}')
    linhas += ["", "✅ aprovado  ⬜ falta aprovar"]
    return "\n".join(linhas)


def resp_saude():
    import saude
    problemas, infos = saude.conferir()
    if not problemas:
        return "✅ <b>Tudo em ordem</b>\n\n" + "\n".join(infos)
    return ("🔧 <b>Precisa de atenção</b>\n\n" + "\n\n".join(problemas)
            + "\n\n" + "\n".join(infos))


def resp_ajuda():
    return ("🔺 <b>Pode me perguntar:</b>\n\n"
            "<b>status</b> — resumo geral\n"
            "<b>proximo</b> — o próximo post com a legenda\n"
            "<b>fila</b> — lista do que vem\n"
            "<b>saude</b> — checagem completa\n\n"
            "Escreva em português normal, eu entendo.")


def entender(texto: str) -> str:
    t = texto.lower().strip().lstrip("/")
    def tem(*palavras):
        return any(p in t for p in palavras)

    if tem("ajuda", "help", "comando", "o que voce faz", "o que vc faz"):
        return resp_ajuda()
    if tem("saude", "saúde", "tudo ok", "tudo bem", "funcionando", "checa", "check"):
        return resp_saude()
    if tem("proximo", "próximo", "prox", "qual o post", "que post"):
        return resp_proximo()
    if tem("fila", "lista", "programado", "agendado", "o que vem"):
        return resp_fila()
    if tem("status", "como esta", "como está", "resumo", "situacao", "situação"):
        return resp_status()
    return resp_status() + "\n\n<i>(mande \"ajuda\" para ver o que pergunto)</i>"


# ---------------------------------------------------------------------------
# Escuta
# ---------------------------------------------------------------------------

def offset() -> int:
    try:
        return int(MARCA.read_text().strip())
    except Exception:
        return 0


def salvar_offset(v: int):
    MARCA.parent.mkdir(parents=True, exist_ok=True)
    MARCA.write_text(str(v))


def uma_rodada(espera=0) -> int:
    """Responde tudo que chegou. Devolve quantos recados atendeu.

    `espera` é a escuta longa (long polling) em segundos: o Telegram segura a
    conexão até chegar recado. Use no modo contínuo — assim uma consulta só
    fica aberta, em vez de várias se atropelando. Duas consultas simultâneas
    com o mesmo token travam uma à outra.
    """
    dono = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    r = _api("getUpdates", offset=offset() + 1, timeout=espera,
             _timeout_http=espera + 15)
    if not r.get("ok"):
        return 0
    atendidos = 0
    ultimo = offset()
    for u in r.get("result", []):
        ultimo = max(ultimo, u["update_id"])
        msg = u.get("message") or u.get("edited_message") or {}
        texto = (msg.get("text") or "").strip()
        chat = str(msg.get("chat", {}).get("id", ""))
        if not texto:
            continue
        if dono and chat != dono:      # só responde ao Luiz
            continue
        print(f'  ← "{texto[:50]}"')
        try:
            responder(entender(texto), chat)
        except Exception as e:
            responder(f"❌ deu erro aqui: {str(e)[:150]}", chat)
        atendidos += 1
    if ultimo > offset():
        salvar_offset(ultimo)
    return atendidos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escutar", action="store_true",
                    help="fica escutando e responde em segundos")
    a = ap.parse_args()

    if not a.escutar:
        n = uma_rodada()
        print(f'{n} recado(s) respondido(s).' if n else "Nada novo.")
        return 0

    print("👂 Escutando o Telegram (Ctrl+C para parar)\n")
    try:
        while True:
            uma_rodada()
            time.sleep(3)
    except KeyboardInterrupt:
        print("\nparei.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
