"""
estado.py — Publica um resumo do cliente onde o bot central possa ler.

Grava `estado.json` no repositório PÚBLICO de mídia, ao lado das artes. É
assim que o bot que escuta o Telegram (um só, no Arco Real) responde sobre
os outros dois clientes sem precisar de acesso aos repositórios privados.

**O que NÃO entra aqui: legenda.** Contagem, data e id de post já são
dedutíveis de quem olhe as artes servidas no mesmo endereço; o texto que
ainda não foi ao ar, não. Manter o resumo magro é o que torna seguro
publicá-lo num lugar aberto.

    ./.venv/bin/python -c "from postador import estado; estado.main()"
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .projeto import raiz

RAIZ = raiz()
POSTS = RAIZ / "posts"
BRT = timezone(timedelta(hours=-3))

import marca  # noqa: E402  (do cliente)


def _ler(nome, padrao):
    p = POSTS / nome
    if not p.exists():
        return padrao
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return padrao


def resumo() -> dict:
    """O retrato do cliente, magro de propósito."""
    plano = _ler("plano.json", [])
    aprov = _ler("aprovado.json", {})
    aprov = aprov.get("posts", aprov)
    feitos = _ler("publicados.json", {})
    falhas = _ler("falhas.json", {})
    agora = datetime.now(BRT)

    fila = []
    for p in plano:
        if p["id"] in feitos:
            continue
        try:
            q = datetime.strptime(p["quando"], "%Y-%m-%d %H:%M").replace(tzinfo=BRT)
        except Exception:
            continue
        fila.append({
            "id": p["id"],
            "quando": p["quando"],
            "tipo": p.get("tipo", "?"),
            "aprovado": aprov.get(p["id"], {}).get("decisao") == "aprovado",
            "futuro": q > agora,
        })
    fila.sort(key=lambda x: x["quando"])
    adiante = [f for f in fila if f["futuro"]]

    # Falha de post que JÁ está no ar não é problema — ele publicou no
    # Instagram e tropeçou depois. Avisar sobre isso todo dia, sem nada a
    # fazer a respeito, é o jeito mais rápido de ensinar alguém a ignorar
    # o alerta de verdade quando ele vier.
    pendentes = {k: v for k, v in falhas.items()
                 if k.split("#")[0] not in feitos}

    dados = {
        "cliente": marca.NOME,
        "chave": marca.CHAVE,
        "arroba": getattr(marca, "ARROBA", ""),
        "atualizado": agora.strftime("%Y-%m-%d %H:%M"),
        "publicados": len(feitos),
        "fila": len(fila),
        "adiante": len(adiante),
        "aprovados": sum(1 for f in adiante if f["aprovado"]),
        "proximo": adiante[0] if adiante else None,
        "atrasados": [f["id"] for f in fila if not f["futuro"]][:5],
        "problemas": [{"post": k, "vezes": v.get("vezes", 1),
                       "erro": str(v.get("erro", ""))[:90]}
                      for k, v in list(pendentes.items())[:5]],
    }

    try:
        from . import meta_api
        c = meta_api._chamar("GET", os.getenv("IG_USER_ID", ""),
                             fields="username,media_count,followers_count")
        dados["meta"] = {"ok": True, "username": c.get("username"),
                         "seguidores": c.get("followers_count"),
                         "posts_no_ar": c.get("media_count")}
    except Exception as e:
        dados["meta"] = {"ok": False, "erro": str(e)[:120]}

    return dados


def publicar_estado() -> bool:
    """Escreve o estado.json no repositório de mídia e envia. Nunca levanta.

    Nunca levanta de propósito: isto roda no fim do workflow de publicação,
    e falhar aqui não pode derrubar um post que já foi ao ar.
    """
    try:
        from . import hospedar
        hospedar.preparar()
        destino = hospedar.ESPELHO / "estado.json"
        novo = json.dumps(resumo(), ensure_ascii=False, indent=2) + "\n"
        if destino.exists() and destino.read_text(encoding="utf-8") == novo:
            print("  estado.json já está em dia.")
            return True
        destino.write_text(novo, encoding="utf-8")
        hospedar._git("add", "estado.json")
        # Quem escreve isto e o robo, nao o Luiz. Assinar com o nome dele
        # faz o historico do repositorio de midia mentir sobre quem agiu —
        # e e justamente onde se vai olhar quando algo sair errado.
        hospedar._git("-c", f"user.name={marca.CHAVE}-bot",
                      "-c", "user.email=bot@enjoystudios.local",
                      "commit", "-q", "-m", "estado: resumo para o bot central")
        r = hospedar.empurrar()
        if r.returncode:
            print(f"  ⚠️ não enviei o estado.json: {r.stderr[:120]}")
            return False
        print(f"  ✓ estado.json no ar em {marca.BASE_MIDIA}/estado.json")
        return True
    # SystemExit NÃO é subclasse de Exception, e `hospedar.preparar()` sai
    # por SystemExit quando não consegue clonar — foi assim que este passo
    # derrubou o workflow em 01/10 em vez de avisar e seguir.
    except (Exception, SystemExit) as e:
        print(f"  ⚠️ não consegui publicar o estado: {str(e)[:160]}")
        print("     (o runner do GitHub só tem permissão no próprio "
              "repositório; ver REFRESCAR_ESTADO em clientes.py)")
        return False


def main():
    print(json.dumps(resumo(), ensure_ascii=False, indent=2))
    return 0
