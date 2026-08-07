"""
meta_api.py — Publicação no Instagram e no Facebook pela Graph API da Meta.

Diferença que manda no desenho do sistema:

  · FACEBOOK  agenda de verdade. Manda-se `scheduled_publish_time` e o post fica
    guardado no servidor da Meta. Depois disso o nosso código pode morrer que o
    post sai igual.

  · INSTAGRAM não agenda. A API só publica agora: cria-se um container em
    /media e publica-se em /media_publish. Por isso existe o `publicar.py`
    rodando de hora em hora — é ele o relógio, não a Meta.

Credenciais no ambiente (ou no .env):
    META_TOKEN        token de página de longa duração (60 dias)
    IG_USER_ID        id da conta Instagram Profissional
    FB_PAGE_ID        id da Página do Facebook
    GRAPH_VERSION     opcional, padrão v25.0
"""
import os
import time
import logging

import requests

log = logging.getLogger("meta")

VERSAO = os.getenv("GRAPH_VERSION", "v25.0")
BASE = f"https://graph.facebook.com/{VERSAO}"

TIMEOUT = 60


class MetaErro(RuntimeError):
    pass


# O token de PÁGINA pode ser invalidado pela Meta sem aviso (app em modo de
# desenvolvimento, mudança de permissão, sessão encerrada). Quando isso acontece
# o post falha silenciosamente na hora marcada. Para não depender de um único
# token, guardamos também o token de USUÁRIO e derivamos um token de página
# novo em tempo de execução se o guardado tiver morrido.
_cache_token = {}


def _valido(tok: str) -> bool:
    try:
        r = requests.get(f"{BASE}/me", params={"access_token": tok},
                         timeout=20).json()
        return "error" not in r
    except Exception:
        return False


def _derivar_da_conta(user_token: str) -> str | None:
    """Pega o token da Página do Arco Real a partir do token de usuário."""
    alvo = os.getenv("FB_PAGE_ID", "").strip()
    try:
        r = requests.get(f"{BASE}/me/accounts",
                         params={"access_token": user_token,
                                 "fields": "id,access_token"}, timeout=30).json()
    except Exception:
        return None
    for pg in r.get("data", []):
        if not alvo or pg.get("id") == alvo:
            return pg.get("access_token")
    return None


def _token():
    if "pagina" in _cache_token:
        return _cache_token["pagina"]

    guardado = os.getenv("META_TOKEN", "").strip()
    if guardado and _valido(guardado):
        _cache_token["pagina"] = guardado
        return guardado

    usuario = os.getenv("META_USER_TOKEN", "").strip()
    if usuario:
        log.warning("[Meta] token de página inválido — derivando do de usuário")
        novo = _derivar_da_conta(usuario)
        if novo and _valido(novo):
            log.info("[Meta] token de página renovado automaticamente")
            _cache_token["pagina"] = novo
            return novo

    if not guardado:
        raise MetaErro("META_TOKEN não está definido")
    raise MetaErro(
        "o token da Meta expirou ou foi invalidado. Refaça em "
        "developers.facebook.com/tools/explorer e rode: python configurar_meta.py")


def _chamar(metodo, caminho, **params):
    params["access_token"] = _token()
    url = f"{BASE}/{caminho.lstrip('/')}"
    r = requests.request(metodo, url, data=params if metodo == "POST" else None,
                         params=None if metodo == "POST" else params, timeout=TIMEOUT)
    try:
        corpo = r.json()
    except ValueError:
        raise MetaErro(f"resposta não-JSON ({r.status_code}): {r.text[:300]}")
    if not r.ok or "error" in corpo:
        erro = corpo.get("error", {})
        raise MetaErro(f'{erro.get("code","?")}/{erro.get("error_subcode","-")} '
                       f'{erro.get("message", r.text[:300])}')
    return corpo


# ---------------------------------------------------------------------------
# Instagram — publica agora, sempre
# ---------------------------------------------------------------------------

def _ig_id():
    v = os.getenv("IG_USER_ID", "").strip()
    if not v:
        raise MetaErro("IG_USER_ID não está definido")
    return v


def _esperar_container(creation_id, tentativas=40, intervalo=15):
    """Publicar antes do container ficar pronto devolve
    "Media ID is not available" (código 9007). Vale para FOTO também, não só
    vídeo: a foto costuma levar poucos segundos, mas leva."""
    for n in range(tentativas):
        info = _chamar("GET", creation_id, fields="status_code,status")
        estado = info.get("status_code")
        if estado == "FINISHED":
            return
        if estado == "ERROR":
            raise MetaErro(f'processamento falhou: {info.get("status")}')
        log.info("[IG] container %s: %s (%d/%d)", creation_id, estado, n + 1, tentativas)
        time.sleep(intervalo)
    raise MetaErro(f"container {creation_id} não ficou pronto a tempo")


def ig_publicar_imagem(image_url, legenda):
    c = _chamar("POST", f"{_ig_id()}/media", image_url=image_url, caption=legenda)
    _esperar_container(c["id"], tentativas=20, intervalo=3)
    return _chamar("POST", f"{_ig_id()}/media_publish", creation_id=c["id"])["id"]


def ig_publicar_carrossel(urls, legenda):
    if not 2 <= len(urls) <= 10:
        raise MetaErro(f"carrossel aceita de 2 a 10 imagens, recebi {len(urls)}")
    filhos = []
    for u in urls:
        f = _chamar("POST", f"{_ig_id()}/media",
                    image_url=u, is_carousel_item="true")["id"]
        _esperar_container(f, tentativas=20, intervalo=3)
        filhos.append(f)
    pai = _chamar("POST", f"{_ig_id()}/media", media_type="CAROUSEL",
                  children=",".join(filhos), caption=legenda)
    _esperar_container(pai["id"], tentativas=20, intervalo=3)
    return _chamar("POST", f"{_ig_id()}/media_publish", creation_id=pai["id"])["id"]


def ig_publicar_reel(video_url, legenda, capa_url=None):
    extra = {"cover_url": capa_url} if capa_url else {}
    c = _chamar("POST", f"{_ig_id()}/media", media_type="REELS",
                video_url=video_url, caption=legenda, **extra)
    _esperar_container(c["id"])
    return _chamar("POST", f"{_ig_id()}/media_publish", creation_id=c["id"])["id"]


# ---------------------------------------------------------------------------
# Facebook — agenda no servidor da Meta
# ---------------------------------------------------------------------------

def _pagina_id():
    v = os.getenv("FB_PAGE_ID", "").strip()
    if not v:
        raise MetaErro("FB_PAGE_ID não está definido")
    return v


def fb_publicar_foto(image_url, legenda, agendar_para=None):
    """`agendar_para` = timestamp UNIX. A Meta exige entre 10 minutos e 6 meses
    à frente; fora disso ela recusa. Sem o parâmetro, publica na hora."""
    p = {"url": image_url, "caption": legenda}
    if agendar_para:
        p["published"] = "false"
        p["scheduled_publish_time"] = int(agendar_para)
    return _chamar("POST", f"{_pagina_id()}/photos", **p)["id"]


def fb_publicar_texto(mensagem, link=None, agendar_para=None):
    p = {"message": mensagem}
    if link:
        p["link"] = link
    if agendar_para:
        p["published"] = "false"
        p["scheduled_publish_time"] = int(agendar_para)
    return _chamar("POST", f"{_pagina_id()}/feed", **p)["id"]


def fb_publicar_video(video_url, descricao, titulo=None, agendar_para=None):
    p = {"file_url": video_url, "description": descricao}
    if titulo:
        p["title"] = titulo
    if agendar_para:
        p["published"] = "false"
        p["scheduled_publish_time"] = int(agendar_para)
    return _chamar("POST", f"{_pagina_id()}/videos", **p)["id"]


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------

def conferir():
    """Valida token e ids antes de confiar o mês inteiro ao sistema."""
    saida = {}
    pagina = _chamar("GET", _pagina_id(), fields="name,username,fan_count")
    saida["facebook"] = pagina
    conta = _chamar("GET", _ig_id(),
                    fields="username,name,followers_count,media_count")
    saida["instagram"] = conta
    debug = requests.get(
        f"{BASE}/debug_token",
        params={"input_token": _token(), "access_token": _token()},
        timeout=TIMEOUT,
    ).json().get("data", {})
    saida["token"] = {
        "tipo": debug.get("type"),
        "expira_em": debug.get("expires_at"),
        "permissoes": debug.get("scopes", []),
    }
    return saida


def ig_validar_imagem(url):
    """Cria um container só para confirmar que o Instagram aceita este endereço.
    Usado pelo carrossel, onde é preciso saber qual URL serve antes de montar."""
    _chamar("POST", f"{_ig_id()}/media", image_url=url, is_carousel_item="true")
    return url
