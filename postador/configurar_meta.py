"""
configurar_meta.py — Configura o acesso ao Instagram e ao Facebook.

Você cola o token UMA vez, aqui no terminal. O script faz o resto:

    · descobre o ID da Página do Facebook
    · descobre o ID da conta do Instagram ligada a ela
    · confere se o token tem todas as permissões necessárias
    · avisa quantos dias faltam para expirar
    · grava no .env
    · cadastra nos Secrets do GitHub (se o gh estiver instalado)

    ./.venv/bin/python configurar_meta.py

O token é digitado escondido e nunca aparece na tela nem no histórico do shell.
"""
import getpass
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

from .projeto import raiz
RAIZ = raiz()
ENV = RAIZ / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(ENV)
except ImportError:
    pass

VERSAO = os.getenv("GRAPH_VERSION", "v25.0")
BASE = f"https://graph.facebook.com/{VERSAO}"

PERMISSOES = [
    "pages_show_list", "pages_read_engagement", "pages_manage_posts",
    "instagram_basic", "instagram_content_publish",
]


def api(caminho, token, **params):
    params["access_token"] = token
    r = requests.get(f"{BASE}/{caminho}", params=params, timeout=40)
    corpo = r.json()
    if "error" in corpo:
        raise SystemExit(f'\n❌ {corpo["error"].get("message")}\n')
    return corpo


def gravar_env(pares):
    linhas = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    for chave, valor in pares.items():
        nova = f"{chave}={valor}"
        for i, l in enumerate(linhas):
            if re.match(rf"^{chave}\s*=", l):
                linhas[i] = nova
                break
        else:
            linhas.append(nova)
    ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def gh_secret(chave, valor):
    try:
        subprocess.run(["gh", "secret", "set", chave, "-b", valor],
                       check=True, capture_output=True, timeout=60)
        return True
    except Exception:
        return False


# App criado no navegador junto com o Luiz. É público (não é segredo).
APP_ID_PADRAO = "1026038863477791"


def trocar_por_longo(token_curto, app_id, app_secret):
    """Troca o token curto (1h) do Graph Explorer por um de longa duração.
    A partir dele, o token de Página vem SEM prazo de expiração."""
    r = requests.get(f"{BASE}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": token_curto,
    }, timeout=40).json()
    if "access_token" not in r:
        raise SystemExit(f'\n❌ Não consegui esticar o token: '
                         f'{r.get("error", {}).get("message", r)}\n')
    return r["access_token"]


def main():
    print(__doc__.split("Você cola")[0])
    print("Cole o token que apareceu no Graph API Explorer (o curto, de 1h).")
    print("Ele não aparece enquanto você digita — cole e dê Enter.\n")
    # o App Secret pode já estar salvo no .env (via chave.py); senão, pergunta
    app_id = os.getenv("META_APP_ID", "").strip() or APP_ID_PADRAO
    app_secret = os.getenv("META_APP_SECRET", "").strip()
    try:
        token = getpass.getpass("Cole o TOKEN do Explorer: ").strip()
        if not token:
            raise SystemExit("Nada colado. Saindo.")
        if not app_secret:
            print("   (o App Secret está em App settings → Basic → botão Show)")
            app_secret = getpass.getpass("Cole o App Secret: ").strip()
    except (EOFError, OSError):  # sem terminal interativo
        raise SystemExit("Rode este script direto no Terminal, não por pipe.")
    if not app_secret:
        raise SystemExit("Sem o App Secret não dá para deixar o token permanente.")

    print("\n🔁 Esticando o token para não expirar…")
    token = trocar_por_longo(token, app_id, app_secret)
    print("   ✓ token de longa duração obtido")

    print("\n🔎 Conferindo o token…")
    debug = requests.get(f"{BASE}/debug_token",
                         params={"input_token": token, "access_token": token},
                         timeout=40).json().get("data", {})
    escopos = debug.get("scopes", [])
    faltando = [p for p in PERMISSOES if p not in escopos]
    if faltando:
        print(f'\n⚠️  Faltam permissões: {", ".join(faltando)}')
        print("   Volte no Graph API Explorer, marque essas e gere de novo.\n")
        if input("Continuar mesmo assim? [s/N] ").lower() != "s":
            return 1

    expira = debug.get("expires_at")
    if expira:
        dias = (datetime.fromtimestamp(expira) - datetime.now()).days
        print(f"   Token expira em {dias} dias.")
        if dias < 30:
            print("   ⚠️  Curto. Use o botão 'Extend Access Token' no Debugger.")
    else:
        print("   Token sem prazo (permanente de página).")

    print("\n🔎 Procurando a Página do Facebook…")
    paginas = api("me/accounts", token, fields="id,name,access_token").get("data", [])
    if not paginas:
        raise SystemExit("\n❌ Nenhuma Página encontrada. O token é de Página mesmo?\n")

    if len(paginas) == 1:
        pagina = paginas[0]
    else:
        for i, p in enumerate(paginas, 1):
            print(f'   {i}. {p["name"]}  ({p["id"]})')
        pagina = paginas[int(input("\nQual é a do Arco Real? ").strip()) - 1]
    print(f'   ✓ {pagina["name"]} — {pagina["id"]}')

    # o token específico da Página é o que publica
    token_pagina = pagina.get("access_token", token)

    print("\n🔎 Procurando o Instagram ligado a ela…")
    liga = api(pagina["id"], token_pagina, fields="instagram_business_account")
    conta = liga.get("instagram_business_account")
    if not conta:
        raise SystemExit(
            "\n❌ Nenhuma conta do Instagram ligada a essa Página.\n"
            "   No app do Instagram: Configurações → Contas vinculadas → Facebook.\n"
            "   E confirme que a conta é Profissional, não pessoal.\n")

    perfil = api(conta["id"], token_pagina,
                 fields="username,followers_count,media_count")
    print(f'   ✓ @{perfil.get("username")} — '
          f'{perfil.get("followers_count", "?")} seguidores, '
          f'{perfil.get("media_count", "?")} publicações')

    # guarda os DOIS: se a Meta invalidar o token de página (acontece sem aviso),
    # o publicar.py deriva um novo a partir do token de usuário e o post sai
    gravar_env({"META_TOKEN": token_pagina,
                "META_USER_TOKEN": token,
                "IG_USER_ID": conta["id"],
                "FB_PAGE_ID": pagina["id"]})
    print("\n✅ Gravado no .env (token de página + de usuário, para recuperação)")

    if input("Cadastrar nos Secrets do GitHub também? [S/n] ").lower() != "n":
        ok = all([gh_secret("META_TOKEN", token_pagina),
                  gh_secret("META_USER_TOKEN", token),
                  gh_secret("IG_USER_ID", conta["id"]),
                  gh_secret("FB_PAGE_ID", pagina["id"])])
        print("✅ Secrets cadastrados" if ok else
              "⚠️  Falhou — rode 'gh auth login' e tente de novo")

    print("\n🎉 Pronto. Agora confirme com:")
    print("   ./.venv/bin/python publicar.py --conferir")
    return 0


if __name__ == "__main__":
    sys.exit(main())
