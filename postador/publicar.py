"""
publicar.py — O relógio do sistema.

O Instagram não guarda post agendado, então este script roda de hora em hora
(GitHub Actions) e pergunta: tem algum post aprovado cuja hora já chegou?
Se tem, publica. Se não, sai calado.

    ./.venv/bin/python publicar.py --conferir   # testa credenciais, não posta
    ./.venv/bin/python publicar.py --simular    # mostra o que faria
    ./.venv/bin/python publicar.py              # publica de verdade
    ./.venv/bin/python publicar.py --forcar p01 # publica um post específico agora

Só publica o que estiver marcado como aprovado em posts/aprovado.json — o
arquivo que o painel de aprovação exporta. Post sem aprovação nunca vai ao ar.
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .projeto import raiz
RAIZ = raiz()
sys.path.insert(0, str(RAIZ))

# No GitHub Actions as credenciais chegam como variáveis de ambiente (Secrets);
# rodando na mão, vêm do .env.
try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

from . import meta_api  # noqa: E402

BRT = timezone(timedelta(hours=-3))
POSTS = RAIZ / "posts"
REGISTRO = POSTS / "publicados.json"

# Folga para o atraso do cron do GitHub Actions, que pode passar de 20 minutos.
# O robô acorda de hora em hora; estas janelas garantem que nenhum horário caia
# num vão entre dois despertares.
ATRASO_TOLERADO = timedelta(minutes=150)
ADIANTAMENTO = timedelta(minutes=20)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(RAIZ / "arcoreal-bot.log"),
                              logging.StreamHandler()])
log = logging.getLogger("publicar")


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

def carregar(caminho, padrao):
    if not Path(caminho).exists():
        return padrao
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def ja_publicados() -> dict:
    return carregar(REGISTRO, {})


def marcar(post_id, resultado):
    reg = ja_publicados()
    reg[post_id] = dict(resultado, em=datetime.now(BRT).isoformat())
    REGISTRO.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def aprovacoes() -> dict:
    """Lê o aprovado.json exportado pelo painel."""
    dados = carregar(POSTS / "aprovado.json", {})
    return dados.get("posts", dados)


# ---------------------------------------------------------------------------
# Registro de falhas — para não avisar o mesmo erro de hora em hora
# ---------------------------------------------------------------------------

FALHAS = POSTS / "falhas.json"
MAX_TENTATIVAS = 3


def _falhas() -> dict:
    return carregar(FALHAS, {})


def registrar_falha(post_id: str, erro: str) -> tuple[int, bool]:
    """Guarda a falha e diz (quantas vezes, devo avisar agora?).

    Avisa na 1ª falha e na última (quando desiste). No meio fica calado: em
    29/07 o mesmo erro de token gerou um alerta por hora e virou ruído.
    """
    d = _falhas()
    reg = d.get(post_id, {"vezes": 0, "erro": ""})
    mesmo_erro = reg.get("erro", "")[:80] == erro[:80]
    reg["vezes"] = reg["vezes"] + 1 if mesmo_erro else 1
    reg["erro"] = erro
    reg["ultima"] = datetime.now(BRT).isoformat()
    d[post_id] = reg
    FALHAS.parent.mkdir(parents=True, exist_ok=True)
    FALHAS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    avisar_agora = reg["vezes"] == 1 or reg["vezes"] == MAX_TENTATIVAS
    return reg["vezes"], avisar_agora


def desistiu(post_id: str) -> bool:
    """Já tentou demais — para de insistir até alguém consertar."""
    return _falhas().get(post_id, {}).get("vezes", 0) >= MAX_TENTATIVAS


def limpar_falhas(post_id: str) -> None:
    d = _falhas()
    if d.pop(post_id, None):
        FALHAS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def avisar(texto):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        return
    try:
        import requests
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": texto,
                            "parse_mode": "HTML", "disable_web_page_preview": "true"},
                      timeout=20)
    except Exception as e:  # aviso nunca derruba a publicação
        log.warning("Telegram falhou: %s", e)


# ---------------------------------------------------------------------------
# Hospedagem da imagem
# ---------------------------------------------------------------------------

def url_publica(caminho: Path):
    """Endereço público da imagem — a Meta baixa dali, não aceita upload.

    Pode devolver uma lista de endereços equivalentes; use `com_urls()` para
    tentar cada um até a Meta aceitar."""
    base = os.getenv("MIDIA_BASE_URL", "").strip()
    if base:
        return f'{base.rstrip("/")}/{caminho.name}'

    chave = os.getenv("IMGBB_API_KEY", "").strip()
    if chave and not chave.startswith("COLOQUE"):
        import base64
        import requests
        r = requests.post("https://api.imgbb.com/1/upload",
                          data={"key": chave,
                                "image": base64.b64encode(caminho.read_bytes())},
                          timeout=120)
        r.raise_for_status()
        d = r.json()["data"]
        # ORDEM IMPORTA. O imgbb devolve endereços diferentes para a mesma
        # imagem e eles NÃO têm a mesma resolução:
        #     url          → a imagem inteira   (1080x1350, 554KB)
        #     display_url  → cópia reduzida     ( 512x640,  100KB)
        # Já publiquei quatro posts em 480x600 por deixar o display_url na
        # frente. Ele só entra como último recurso, quando o Instagram recusa
        # o original com "Only photo or video can be accepted as media type".
        candidatas = [d.get("url"), (d.get("image") or {}).get("url"),
                      d.get("display_url")]
        vistas, saida = set(), []
        for u in candidatas:
            if u and u not in vistas:
                vistas.add(u)
                saida.append(u)
        if not saida:
            raise RuntimeError(f"imgbb não devolveu URL utilizável: {d}")
        return saida if len(saida) > 1 else saida[0]

    raise RuntimeError(
        "Sem lugar para hospedar a imagem. Defina MIDIA_BASE_URL (pasta pública "
        "no GitHub Pages) ou IMGBB_API_KEY (grátis em api.imgbb.com)."
    )


# ---------------------------------------------------------------------------
# Publicação
# ---------------------------------------------------------------------------

class ReelSemVideo(Exception):
    """Reel aprovado cujo vídeo ainda não foi produzido — espera, não falha."""


def primeiro(x):
    return x[0] if isinstance(x, list) else x


def video_no_ar(url):
    """O vídeo responde no endereço público? É de lá que a Meta baixa.

    HEAD basta e não puxa os 55 MB. Se a rede falhar, devolve True: melhor
    tentar publicar e receber o erro real da Meta do que pular calado — foi
    justamente o silêncio que fez um reel pronto perder o horário.
    """
    try:
        import requests
        r = requests.head(url, timeout=30, allow_redirects=True)
        if r.status_code == 200:
            return True
        log.warning("[reel] %s respondeu %s", url[:70], r.status_code)
        return False
    except Exception as e:
        log.warning("[reel] não consegui conferir %s: %s", url[:70], e)
        return True


LARGURA_MINIMA = 1000     # o feed do Instagram entrega 1080; abaixo disso borra


def conferir_resolucao(url, esperado=None):
    """Confirma que o endereço serve a imagem inteira, não uma cópia reduzida.

    O imgbb devolve `url` (inteira) e `display_url` (512px). Quatro posts foram
    ao ar em 480x600 porque a cópia reduzida entrou sem ninguém perceber.
    """
    import io
    try:
        import requests
        from PIL import Image
        r = requests.get(url, timeout=60)
        larg, alt = Image.open(io.BytesIO(r.content)).size
    except Exception as e:
        log.warning("[imagem] não consegui conferir %s: %s", url[:50], e)
        return True          # na dúvida, deixa seguir — a Meta valida depois
    if larg < LARGURA_MINIMA:
        log.error("[imagem] ❌ %dx%d é pequeno demais — %s", larg, alt, url[:60])
        return False
    if esperado and larg < esperado[0]:
        log.warning("[imagem] servida em %dx%d, menor que o arquivo (%dx%d)",
                    larg, alt, *esperado)
    return True


def com_urls(enderecos, acao):
    """Tenta a ação com cada endereço da imagem até um funcionar.

    Endereço que sirva imagem reduzida é pulado ANTES de tentar publicar —
    melhor falhar e avisar do que colocar no ar um post borrado.
    """
    lista = enderecos if isinstance(enderecos, list) else [enderecos]
    ultimo = None
    for i, url in enumerate(lista, 1):
        if not conferir_resolucao(url):
            ultimo = RuntimeError(f"endereço serve imagem reduzida: {url}")
            continue
        try:
            return acao(url)
        except Exception as e:
            ultimo = e
            if i < len(lista):
                log.warning("[Meta] endereço %d recusado (%s) — tentando o próximo",
                            i, str(e)[:60])
    raise ultimo


def publicar_post(post, legenda, simular=False):
    tipo = post["tipo"]
    imagem = RAIZ / post["imagem"]

    if tipo == "reel":
        video = post.get("video")
        if not video:
            raise ReelSemVideo(
                f'{post["id"]}: reel aprovado, mas sem vídeo definido no plano.')
        # NÃO conferir se o arquivo está no disco. O .gitignore exclui
        # reels/*.mp4 (são dezenas de MB), então o robô do GitHub Actions
        # baixa o repositório SEM o vídeo e concluía "ainda não existe" para um
        # reel que estava pronto e no ar. Foi assim que o reel de 03/08 perdeu
        # as 7h e só saiu 10h. O que importa é o endereço público, que é de
        # onde a Meta baixa — então é ele que tem de responder.
        if not video_no_ar(primeiro(url_publica(RAIZ / video))):
            raise ReelSemVideo(
                f'{post["id"]}: o vídeo ainda não está no ar em {video}.')

    if simular:
        log.info("[SIMULAÇÃO] %s (%s) — %s", post["id"], tipo, post["quando"])
        log.info("            %s", legenda.replace("\n", " ⏎ ")[:150])
        return {"simulado": True}

    quando = datetime.strptime(post["quando"], "%Y-%m-%d %H:%M").replace(tzinfo=BRT)
    resultado = {}

    def primeira(x):
        return x[0] if isinstance(x, list) else x

    if tipo == "carrossel":
        # cada slide pode ter vários endereços; escolhe o que a Meta aceitar
        urls = []
        for i in range(len(post["carrossel"])):
            cands = url_publica(RAIZ / "posts" / "imagens" / f'{post["id"]}_{i}.jpg')
            urls.append(com_urls(cands, lambda u: meta_api.ig_validar_imagem(u)))
        resultado["instagram"] = meta_api.ig_publicar_carrossel(urls, legenda)
        resultado["facebook"] = meta_api.fb_publicar_foto(urls[0], legenda)

    elif tipo == "reel":
        url_video = primeira(url_publica(RAIZ / post["video"]))
        url_capa = primeira(url_publica(imagem))
        resultado["instagram"] = meta_api.ig_publicar_reel(url_video, legenda, url_capa)
        resultado["facebook"] = meta_api.fb_publicar_video(url_video, legenda)

    else:  # foto e card
        url = url_publica(imagem)
        resultado["instagram"] = com_urls(
            url, lambda u: meta_api.ig_publicar_imagem(u, legenda))
        url = primeira(url)
        # o Facebook aceita agendamento nativo se a hora ainda não chegou
        agenda = None
        agora = datetime.now(BRT)
        if quando > agora + timedelta(minutes=15):
            agenda = quando.timestamp()
        resultado["facebook"] = meta_api.fb_publicar_foto(url, legenda, agenda)

    return resultado


def rodar(simular=False, forcar=None):
    plano_json = POSTS / "plano.json"
    if not plano_json.exists():
        raise SystemExit("posts/plano.json não existe. Rode: python montar.py")

    fila = json.loads(plano_json.read_text(encoding="utf-8"))
    decisoes = aprovacoes()
    feitos = ja_publicados()
    agora = datetime.now(BRT)

    pendentes = []
    for post in fila:
        pid = post["id"]
        if pid in feitos:
            continue
        if forcar:
            if pid == forcar:
                pendentes.append(post)
            continue
        decisao = decisoes.get(pid, {})
        if decisao.get("decisao") != "aprovado":
            continue
        if desistiu(pid):
            log.info("%s: já falhou %d vezes, não vou insistir. Conserte e rode "
                     "com --forcar.", pid, MAX_TENTATIVAS)
            continue
        quando = datetime.strptime(post["quando"], "%Y-%m-%d %H:%M").replace(tzinfo=BRT)
        if quando - ADIANTAMENTO <= agora <= quando + ATRASO_TOLERADO:
            pendentes.append(post)

    if not pendentes:
        log.info("Nada a publicar agora (%s).", agora.strftime("%d/%m %H:%M"))
        return

    for post in pendentes:
        pid = post["id"]
        legenda = decisoes.get(pid, {}).get("legenda") or post["legenda"]
        try:
            resultado = publicar_post(post, legenda, simular)
            if not simular:
                marcar(pid, resultado)
                limpar_falhas(pid)
                limpar_falhas(f"{pid}#sem-video")
                # memória longa: impede repetir isso em qualquer mês futuro
                from . import historico
                historico.registrar(post, legenda, agora.strftime("%d/%m/%Y"))
                avisar(f'✅ <b>{pid}</b> publicado\n'
                       f'{post["dia_semana"]} {post["quando_br"]} · {post["tipo"]}\n'
                       f'IG: <code>{resultado.get("instagram","—")}</code>\n'
                       f'FB: <code>{resultado.get("facebook","—")}</code>')
            log.info("✅ %s publicado: %s", pid, resultado)
        except ReelSemVideo as e:
            log.info("⏳ %s", e)
            # Esperar calado só vale ANTES da hora marcada. Depois dela, o
            # silêncio vira prejuízo: o reel de 03/08 devia sair 7h, ficou
            # parado o dia todo sem um aviso, e só saiu 10h quando o Luiz
            # percebeu na mão. Passou da hora, ele é avisado.
            quando = datetime.strptime(post["quando"], "%Y-%m-%d %H:%M").replace(tzinfo=BRT)
            if agora > quando:
                # Chave separada de propósito: contada junto com as falhas
                # reais, a terceira espera acionaria `desistiu(pid)` e o reel
                # nunca mais sairia — nem depois de o vídeo subir. Aqui o
                # contador só serve para não repetir o alerta toda hora.
                _, avisar_agora = registrar_falha(f"{pid}#sem-video", str(e))
                if avisar_agora:
                    atraso = int((agora - quando).total_seconds() // 60)
                    avisar(f'⏳ <b>{pid}</b> perdeu a hora — {atraso} min de atraso\n'
                           f'{post["dia_semana"]} {post["quando_br"]}\n\n'
                           f'<code>{str(e)[:200]}</code>\n\n'
                           f'O vídeo precisa estar no ar em MIDIA_BASE_URL. '
                           f'Rode <code>python hospedar.py</code>.')
            continue
        except Exception as e:
            vezes, avisar_agora = registrar_falha(pid, str(e))
            log.error("❌ %s falhou (tentativa %d/%d): %s",
                      pid, vezes, MAX_TENTATIVAS, e)
            if not avisar_agora:
                log.info("   (mesmo erro de antes — não vou repetir o alerta)")
                continue
            if vezes >= MAX_TENTATIVAS:
                avisar(f'🛑 <b>{pid} desistiu</b> após {vezes} tentativas\n'
                       f'{post["dia_semana"]} {post["quando_br"]}\n\n'
                       f'<code>{str(e)[:300]}</code>\n\n'
                       f'Não vou mais tentar até isso ser corrigido.')
            else:
                avisar(f'❌ <b>{pid}</b> NÃO foi publicado\n'
                       f'{post["dia_semana"]} {post["quando_br"]}\n\n'
                       f'<code>{str(e)[:300]}</code>\n\n'
                       f'Vou tentar de novo na próxima hora.')


def main():
    ap = argparse.ArgumentParser(description="Publica os posts do Arco Real.")
    ap.add_argument("--conferir", action="store_true",
                    help="testa token, conta e página; não publica nada")
    ap.add_argument("--simular", action="store_true",
                    help="mostra o que seria publicado agora")
    ap.add_argument("--forcar", metavar="ID",
                    help="publica um post específico agora, ignorando o horário")
    ap.add_argument("--marcar", metavar="ID",
                    help="marca como já publicado À MÃO — o agendador pula, e o "
                         "versículo e o fundo ficam queimados para sempre")
    args = ap.parse_args()

    if args.marcar:
        fila = json.loads((POSTS / "plano.json").read_text(encoding="utf-8"))
        post = next((p for p in fila if p["id"] == args.marcar), None)
        if not post:
            raise SystemExit(f"Post {args.marcar} não existe no plano.")
        agora = datetime.now(BRT)
        marcar(args.marcar, {"manual": True})
        from . import historico
        historico.registrar(post, post["legenda"], agora.strftime("%d/%m/%Y"))
        print(f'✅ {args.marcar} marcado como publicado à mão em '
              f'{agora.strftime("%d/%m/%Y %H:%M")}.')
        print("   O agendador vai ignorá-lo, e nada vai repetir esse conteúdo.")
        return

    if args.conferir:
        info = meta_api.conferir()
        print(json.dumps(info, ensure_ascii=False, indent=2))
        expira = info["token"].get("expira_em")
        if expira:
            dias = (datetime.fromtimestamp(expira, BRT) - datetime.now(BRT)).days
            print(f"\n⏳ Token expira em {dias} dias.")
            if dias < 10:
                print("⚠️  Renove antes que a fila pare.")
        return

    rodar(simular=args.simular, forcar=args.forcar)


if __name__ == "__main__":
    main()
