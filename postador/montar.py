"""
montar.py — Renderiza todos os posts do plano e gera o painel de aprovação.

    ./.venv/bin/python montar.py

Gera:
    posts/imagens/pNN.jpg      arte pronta para publicar (1080x1350)
    posts/plano.json           o plano com as legendas montadas
    posts/aprovacao.html       painel para o Luiz aprovar ou pedir ajuste

O painel guarda as decisões no localStorage e exporta `aprovado.json`,
que é o arquivo que o publisher lê para postar.
"""
import base64
import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import bancos, render
from .projeto import conferir, raiz

# Falha explicando ANTES do import de `plano`, que sem isto quebraria com um
# "ModuleNotFoundError: plano" — mensagem que não diz o que fazer.
conferir()

# `plano` e `marca` são DO CLIENTE. Vêm da pasta de onde o comando foi chamado,
# que o Python põe no sys.path. Cada cliente tem os seus.
import plano   # noqa: E402
import marca   # noqa: E402

RAIZ = raiz()
FOTOS = RAIZ / marca.PASTA_FOTOS
ENTRADA = RAIZ / "entrada"      # onde o cliente larga arquivo feito à mão
SAIDA = RAIZ / "posts"
IMAGENS = SAIDA / "imagens"
MASTERS = SAIDA / "masters4k"   # arquivo grande para reels, impressão e reuso

# As DUAS páginas que o Luiz abre ficam juntas, longe do resto. `posts/` tem
# doze arquivos de trabalho do robô e ele se perdia procurando as duas que
# interessam.
PASTA_PAINEL = RAIZ / "Painel"   # PAINEL já é o template HTML lá embaixo

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _estilo_industrial():
    """O cliente pediu outro estilo? `marca.ESTILO = "industrial"`.

    Sem isso, arte de cliente técnico sai com serifa capitular e moldura
    ornamentada — o vocabulário do Arco Real, que é de irmandade.
    """
    return getattr(marca, "ESTILO", "classico") == "industrial"


def renderizar_slide(post, i, slide) -> Path:
    """Um slide do carrossel: pNN_0.jpg, pNN_1.jpg…"""
    destino = IMAGENS / f'{post["id"]}_{i}.jpg'

    # Arte já finalizada fora daqui entra INTACTA — nada é desenhado por cima.
    # Sem isto, peça pronta feita à mão receberia logo e título de novo,
    # duplicados. O arquivo fica em entrada/artes/.
    if slide.get("pronto"):
        origem = ENTRADA / "artes" / slide["pronto"]
        if not origem.exists():
            raise SystemExit(f'arte pronta não achada: {origem}')
        shutil.copy2(origem, destino)
        print(f'  ✓ arte pronta: {slide["pronto"]}')
        return destino

    if _estilo_industrial() and slide["foto"] != plano.CARD:
        from . import industrial
        return industrial.gerar(
            FOTOS / slide["foto"], destino,
            etiqueta=slide.get("etiqueta"), titulo=slide.get("titulo"),
            lower=slide.get("lower"),
            cortar_topo=slide.get("cortar_topo", 0.0))
    if slide["foto"] == plano.CARD:
        return render.gerar_card(destino, slide["texto"], slide["titulo"],
                                 chamada=f"{marca.ARROBA} · {marca.LOCAL}", aspas=False,
                                 fundo=bancos.escolher(slide.get("fundo", "")))
    return render.gerar(
        foto=FOTOS / slide["foto"], saida=destino, titulo=slide.get("titulo"),
        lower=tuple(slide["lower"]) if slide.get("lower") else None,
    )


def capa_do_video(video: Path, destino: Path, quando=None):
    """Capa do reel tirada do próprio vídeo, em 9:16.

    O card de versículo sai em 1080x1350 (4:5) e o Instagram corta capa de reel
    para 9:16 — o card chegaria mutilado na grade. Um quadro do vídeo já nasce
    na proporção certa e ainda mostra do que o reel se trata.

    Por padrão pega o quadro logo depois da última legenda: dali para frente a
    tela está limpa, e é onde fica o emblema aceso.
    """
    if not video.exists():
        return None
    if quando is None:
        blocos = []
        arq = RAIZ / "reels" / "legendas" / f"{video.stem}.py"
        if arq.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("b", arq)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            blocos = m.BLOCOS
        quando = (blocos[-1][1] + 3) if blocos else 1.0

    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{quando:.2f}",
         "-i", str(video), "-frames:v", "1", "-q:v", "1", str(destino)],
        capture_output=True, text=True)
    if r.returncode or not destino.exists():
        print(f"  ⚠️ não consegui tirar a capa de {video.name} — usando o card")
        return None
    return destino


def renderizar(post: dict) -> Path:
    destino = IMAGENS / f'{post["id"]}.jpg'
    mestre = MASTERS / f'{post["id"]}.jpg'
    tema = plano.FUNDOS.get(post["id"])
    fundo = bancos.escolher(tema) if tema else None

    if post["tipo"] == "carrossel":
        capas = [renderizar_slide(post, i, s) for i, s in enumerate(post["carrossel"])]
        return capas[0]

    if post["tipo"] == "reel":
        # capa feita à mão ganha do quadro automático, sempre
        manual = ENTRADA / f'capa-{post["id"]}.jpg'
        if manual.exists():
            shutil.copy2(manual, destino)
            print(f'  ✓ capa manual: {manual.name}')
            return destino
        if post.get("video"):
            capa = capa_do_video(RAIZ / post["video"], destino)
            if capa:
                return capa

    if post["tipo"] in ("card", "reel"):
        # card sem versículo usa a citação do Ritual; sem nenhum dos dois,
        # o próprio corpo vira a arte
        ref, texto = (post.get("versiculo") or post.get("citacao")
                      or ["", post["corpo"]])
        chamada = (post["titulo"] if post["tipo"] == "reel"
                   else plano.NOME_OFICIAL)
        return render.gerar_card(destino, texto, ref, chamada=chamada,
                                 fundo=fundo, master=mestre)

    return render.gerar(
        foto=FOTOS / post["foto"],
        saida=destino,
        master=mestre,
        titulo=post.get("titulo"),
        lower=tuple(post["lower"]) if post.get("lower") else None,
        cortar_rodape=post.get("cortar_rodape", 0.0),
        cortar_topo=post.get("cortar_topo", 0.0),
    )


def miniatura(caminho: Path, largura=1080) -> str:
    """Embute a imagem no HTML — o painel abre offline, sem servidor.

    Resolução cheia (1080) de propósito: é por esta prévia que o Luiz julga a
    arte, E é dela que sai o download direto. Ter a imagem embutida em base64
    permite que o botão "baixar" salve na pasta Downloads sem abrir o navegador
    (o modo arquivo-local bloqueia baixar de caminho relativo)."""
    from PIL import Image
    import io
    im = Image.open(caminho)
    im.thumbnail((largura, largura * 4), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90, subsampling=0, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    problemas = plano.validar()
    if problemas:
        print("❌ Regras violadas — nada foi renderizado:")
        for e in problemas:
            print("  •", e)
        raise SystemExit(1)

    IMAGENS.mkdir(parents=True, exist_ok=True)
    MASTERS.mkdir(parents=True, exist_ok=True)
    fila = []
    # ordem cronológica: o número do post no painel tem que bater com a ordem
    # em que ele vai ao ar, senão "o post 18" não quer dizer nada
    for post in sorted(plano.PLANO, key=lambda p: p["quando"]):
        caminho = renderizar(post)
        quando = datetime.strptime(post["quando"], "%Y-%m-%d %H:%M")
        item = dict(post)
        item["legenda"] = plano.legenda(post)
        item["imagem"] = str(caminho.relative_to(RAIZ))
        item["dia_semana"] = DIAS[quando.weekday()]
        item["quando_br"] = quando.strftime("%d/%m/%Y às %Hh").replace(" às 0", " às ")
        fila.append(item)
        print(f'  ✓ {post["id"]}  {item["dia_semana"]:8} {item["quando_br"]}')

    (SAIDA / "plano.json").write_text(
        json.dumps(fila, ensure_ascii=False, indent=2), encoding="utf-8")

    html = montar_painel(fila)
    conferir_js(html)          # nunca gravar um painel que não roda
    PASTA_PAINEL.mkdir(exist_ok=True)
    (PASTA_PAINEL / "aprovar.html").write_text(html, encoding="utf-8")
    print(f"\n✅ {len(fila)} posts → Painel/aprovar.html")

    # Sobe as artes NA HORA, sem depender de alguém lembrar do hospedar.py.
    # A Meta não recebe arquivo: ela BAIXA do endereço público. Arte renderizada
    # e não hospedada é post que falha com 9004 "Only photo or video can be
    # accepted" — foi o que matou o p27 no dia 06/08. Renderizar e hospedar são
    # um passo só; separá-los foi um convite ao esquecimento.
    try:
        from . import hospedar
        print()
        hospedar.enviar()
    except Exception as e:
        print(f"\n⚠️  Não consegui hospedar agora: {e}")
        print("   Rode à mão antes da hora do post:")
        print("   ./.venv/bin/python hospedar.py")


def conferir_js(html: str) -> None:
    """Valida o JavaScript do painel antes de gravar.

    Existe porque um `\\n` mal escapado no template Python vira quebra de linha
    de verdade dentro de uma string JS e derruba o painel inteiro em silêncio —
    o navegador não avisa, só para de funcionar. Aconteceu uma vez; não de novo.
    """
    import re
    import shutil
    import subprocess
    import tempfile

    js = re.search(r"<script>(.*?)</script>", html, re.S)
    if not js:
        raise SystemExit("❌ painel sem <script>")

    node = shutil.which("node")
    if not node:                       # sem node: pelo menos as aspas soltas
        for n, linha in enumerate(js.group(1).splitlines(), 1):
            if linha.count("'") % 2 or linha.count('"') % 2:
                if "//" not in linha and "`" not in linha:
                    print(f"  ⚠️  linha {n} do JS com aspas ímpares: {linha.strip()[:60]}")
        return

    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8",
                                     delete=False) as f:
        f.write(js.group(1))
        caminho = f.name
    r = subprocess.run([node, "--check", caminho], capture_output=True, text=True)
    Path(caminho).unlink(missing_ok=True)
    if r.returncode:
        print("❌ O JavaScript do painel está quebrado — nada foi gravado:\n")
        print(r.stderr[:900])
        raise SystemExit(1)
    print("  ✓ JavaScript do painel validado")


def montar_painel(fila: list) -> str:
    publicados = {}
    reg = SAIDA / "publicados.json"
    if reg.exists():
        publicados = json.loads(reg.read_text(encoding="utf-8"))

    cartoes = []
    for i, p in enumerate(fila):
        img = miniatura(RAIZ / p["imagem"])
        etiqueta = {"foto": "Foto", "card": "Reflexão", "reel": "REEL",
                    "carrossel": "Carrossel"}[p["tipo"]]
        nota = f'<p class="nota">⚠️ {p["nota"]}</p>' if p.get("nota") else ""
        extra = ""
        if p["tipo"] == "reel":
            extra = ('<p class="nota">🎬 A imagem é só a capa. O vídeo será '
                     'produzido no Higgsfield quando os créditos entrarem.</p>')
        if p["tipo"] == "carrossel":
            extra = f'<p class="nota">🖼 Carrossel de {len(p["carrossel"])} fotos.</p>'
        numero = f"POST {i + 1:02d}"
        # reel sem vídeo produzido: o publisher falha, então sinaliza no HTML
        semvideo = (' data-semvideo="1"'
                    if p["tipo"] == "reel" and not p.get("video") else "")
        base = numero.replace(" ", "")

        # carrossel: embute todos os slides para navegar e baixar todos
        slides = [Path(p["imagem"]).name]
        if p["tipo"] == "carrossel":
            slides = [f'{p["id"]}_{n}.jpg' for n in range(len(p["carrossel"]))]
        imgs = [miniatura(IMAGENS / s) for s in slides]

        # cada slide guarda a própria imagem base64 (src) + o nome do arquivo de
        # download; o JS baixa direto disso, sem passar pelo navegador
        galeria = "".join(
            f'<img class="slide{" atual" if n == 0 else ""}" src="{src}" '
            f'data-baixar="{base}-{p["id"]}{"" if len(imgs) == 1 else f"-{n + 1}"}.jpg" '
            f'alt="slide {n + 1}">'
            for n, src in enumerate(imgs))
        setas = (f'<div class="setas"><button class="ant">‹</button>'
                 f'<span class="cont">1 / {len(slides)}</span>'
                 f'<button class="prox">›</button></div>'
                 if len(slides) > 1 else "")
        if len(slides) > 1:
            links = ('<button class="baixar todas">⬇ Baixar as '
                     f'{len(slides)} do carrossel</button>'
                     '<button class="baixar atual-baixar">⬇ Baixar só o slide '
                     'que estou vendo</button>')
        else:
            links = '<button class="baixar unica">⬇ Baixar imagem (1080×1350)</button>'

        # post que já foi ao ar não pode ser republicado — fica travado no painel
        feito = publicados.get(p["id"])
        if feito:
            quando_saiu = feito.get("em", "")[:10].replace("T", " ")
            nota = (f'<p class="nota jafoi">🔒 JÁ PUBLICADO'
                    f'{" em " + quando_saiu if quando_saiu else ""} — travado, '
                    f'não vai repetir.</p>') + nota

        cartoes.append(f"""
<article class="post{' jafoi' if feito else ''}" data-id="{p['id']}" data-numero="{numero}"{' data-jafoi="1"' if feito else ''}>
  <div class="arte">
    <div class="galeria">{galeria}</div>
    {setas}
    <div class="baixas">{links}</div>
  </div>
  <div class="lado">
    <div class="cab">
      <span class="numero">{numero}</span>
      <span class="tag t-{p['tipo']}">{etiqueta}</span>
      <span class="quando">{p['dia_semana']} · {p['quando_br']}</span>
      <span class="id">{p['id']}</span>
    </div>
    {nota}{extra}
    <label>Legenda</label>
    <textarea class="cap" rows="9">{p['legenda']}</textarea>
    <p class="conta"></p>
    <div class="textos">
      <button class="copiar">📋 Copiar legenda</button>
      <button class="baixartxt">⬇ Baixar .txt</button>
    </div>
    <div class="acoes">
      <button class="ok">✅ Aprovar</button>
      <button class="edit">✏️ Preciso ajustar</button>
    </div>
    <div class="obsbox hidden">
      <label>O que devo mudar nesta legenda?</label>
      <textarea class="obs" rows="3" placeholder="Ex: deixa mais curto · troca o versículo por um de Ageu · tira o nome do Companheiro · tom mais celebrativo"></textarea>
      <div class="textos">
        <button class="enviar">✨ Enviar e reescrever agora</button>
        <button class="desfazer" disabled>↺ Desfazer</button>
      </div>
      <p class="aviso">Reescreve a legenda na hora. Para trocar imagem, virar
      carrossel ou mudar horário, escreva aqui mesmo e me avise no chat — isso
      eu faço no código.</p>
    </div>
    <p class="estado"></p>
  </div>
</article>""")

    contas = Counter(p["tipo"] for p in fila)
    rotulos = [("foto", "📷", "fotos de Capítulos"),
               ("card", "✨", "cards de reflexão"),
               ("reel", "🎬", "reels das 12 Tribos"),
               ("carrossel", "🖼", "carrossel institucional")]
    chips = [f'<span class="chip">{ic} {contas[t]} {txt}</span>'
             for t, ic, txt in rotulos if contas[t]]
    chips.append('<span class="chip">🚫 nenhuma data citada</span>')
    periodo = (f'{fila[0]["quando_br"].split(" às")[0][:5]} a '
               f'{fila[-1]["quando_br"].split(" às")[0][:5]}')
    return (PAINEL.replace("{{CARTOES}}", "\n".join(cartoes))
                  .replace("{{CHIPS}}", "\n    ".join(chips))
                  .replace("{{PERIODO}}", periodo)
                  .replace("{{TOTAL}}", str(len(fila)))
                  .replace("{{NOME}}", marca.NOME)
                  .replace("{{ARROBA}}", marca.ARROBA)
                  .replace("{{CHAVE}}", marca.CHAVE)
                  .replace("{{REGRAS}}", marca.REGRAS)
                  .replace("{{NOME_OFICIAL}}", marca.NOME_OFICIAL))


PAINEL = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aprovação · {{NOME}}</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;900&family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0b0b12;--panel:#13131c;--line:#222232;--txt:#ede9f6;--muted:#8a87a0;--red:#ce2644;--gold:#d4af5a;--green:#4fd870}
body{background:var(--bg);color:var(--txt);font-family:'Montserrat',sans-serif;font-size:14px;padding:28px 20px 90px}
header{max-width:1180px;margin:0 auto 26px}
h1{font-family:'Cinzel';font-size:26px;letter-spacing:.5px}
.sub{color:var(--muted);margin-top:6px;line-height:1.6}
.resumo{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.chip{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:12.5px;font-weight:600}
.post{max-width:1180px;margin:0 auto 20px;display:flex;gap:22px;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}
.post.aprovado{border-color:var(--green)}
.post.ajustar{border-color:var(--gold)}
.arte{flex-shrink:0}
.arte img{width:380px;border-radius:10px;display:block;cursor:zoom-in}
.galeria{position:relative;width:380px}
.galeria .slide{display:none}
.galeria .slide.atual{display:block}
.setas{display:flex;align-items:center;justify-content:center;gap:12px;margin-top:7px;width:380px}
.setas button{background:#0d0d16;border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:4px 14px;font-size:17px;line-height:1.2}
.setas button:hover{border-color:var(--gold)}
.cont{font-size:12px;color:var(--muted);font-weight:600;min-width:52px;text-align:center}
.baixas{display:flex;flex-direction:column;gap:5px;margin-top:8px;width:380px}
.obsbox{margin-top:10px}
.aviso{font-size:11px;color:#55536a;line-height:1.5;margin-top:7px}
.enviar{background:linear-gradient(135deg,var(--red),#8e1b30)!important;color:#fff!important}
.enviar:disabled{opacity:.45}
.aichip{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:600;margin-left:auto}
.aidot{width:8px;height:8px;border-radius:50%}
.aidot.on{background:var(--green);box-shadow:0 0 6px var(--green)}
.aidot.off{background:var(--red)}
.chaveboxe{max-width:1180px;margin:0 auto 18px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px 18px}
.chaveboxe input{width:100%;background:#0d0d16;border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:9px 11px;font-family:'Montserrat';font-size:13px;margin-top:7px}
.chaveboxe .textos{max-width:420px}
.comando{max-width:1180px;margin:0 auto 20px;background:linear-gradient(135deg,#171522,#13131c);border:1px solid var(--gold);border-radius:14px;padding:16px 18px}
.comando label{color:var(--gold);font-size:11.5px;font-weight:700}
.comando textarea{width:100%;background:#0b0b13;border:1px solid var(--line);color:var(--txt);border-radius:9px;padding:11px;font-family:'Montserrat';font-size:13.5px;line-height:1.6;margin-top:6px}
.comando textarea:focus{outline:none;border-color:var(--gold)}
.comando .textos{max-width:420px}
#mandar{background:linear-gradient(135deg,var(--gold),#b8902f)!important;color:#1a1206!important;font-weight:700}
#mandar:disabled{opacity:.45}
.resposta{margin-top:12px;background:#0b0b13;border-left:3px solid var(--gold);border-radius:0 9px 9px 0;padding:12px 14px;font-size:13.5px;line-height:1.65;white-space:pre-wrap}
.resposta.erro{border-left-color:var(--red)}
.feito{display:block;margin-top:8px;font-size:12.5px;color:var(--green);font-weight:600}
.pendente{display:block;margin-top:8px;font-size:12.5px;color:var(--gold);font-weight:600}
.post.mudou{border-color:var(--gold);box-shadow:0 0 0 1px var(--gold)}
.filtros{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
.filtro{background:var(--panel);border:1px solid var(--line);color:var(--muted);border-radius:999px;padding:7px 16px;font-size:12.5px;font-weight:600;cursor:pointer;font-family:'Montserrat'}
.filtro:hover{border-color:var(--gold)}
.filtro.ativo{background:linear-gradient(135deg,var(--red),#8e1b30);color:#fff;border-color:transparent}
.post.oculto{display:none}
.baixar{display:block;width:100%;text-align:center;background:#0d0d16;border:1px solid var(--line);border-radius:8px;padding:8px;font-size:11.5px;font-weight:600;color:var(--gold);text-decoration:none;cursor:pointer;font-family:'Montserrat'}
.baixar:hover{border-color:var(--gold)}
.lado{flex:1;min-width:0;display:flex;flex-direction:column}
.cab{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.tag{font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;text-transform:uppercase;letter-spacing:.5px}
.t-foto{background:#1d2b5c;color:#a9c0ff}
.t-card{background:#3a2d10;color:var(--gold)}
.t-reel{background:#4a1024;color:#ff8fa8}
.t-carrossel{background:#123a2c;color:#7fe0b4}
.quando{color:var(--gold);font-weight:600;font-size:13px}
.id{color:#44425a;font-size:12px;margin-left:auto}
.numero{font-family:'Cinzel';font-weight:900;font-size:15px;color:var(--txt);background:linear-gradient(135deg,var(--red),#8e1b30);padding:5px 12px;border-radius:7px;letter-spacing:.5px}
.textos{display:flex;gap:8px;margin-top:9px}
.textos button{flex:1;background:#0d0d16;border:1px solid var(--line);color:var(--gold);font-size:12px;padding:9px}
.textos button:hover{border-color:var(--gold)}
label{display:block;font-size:10.5px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);margin:8px 0 5px}
textarea{width:100%;background:#0d0d16;border:1px solid var(--line);color:var(--txt);border-radius:9px;padding:11px;font-family:'Montserrat';font-size:13.5px;line-height:1.6;resize:vertical}
textarea:focus{outline:none;border-color:var(--gold)}
.hidden{display:none}
.conta{font-size:11px;color:var(--muted);margin-top:5px}
.conta.longa{color:var(--red);font-weight:600}
.acoes{display:flex;gap:9px;margin-top:11px}
button{border:0;border-radius:9px;padding:10px 18px;font-weight:700;font-size:13px;cursor:pointer;font-family:'Montserrat'}
.ok{background:linear-gradient(135deg,#2f9e52,#1d7a3c);color:#fff}
.edit{background:#0d0d16;border:1px solid var(--line);color:var(--txt)}
button:active{transform:scale(.98)}
.estado{margin-top:9px;font-size:12.5px;font-weight:600}
.nota{background:#1a1626;border-left:3px solid var(--gold);padding:8px 11px;border-radius:0 7px 7px 0;font-size:12.5px;color:#c9c4de;margin-bottom:8px;line-height:1.5}
.barra{position:fixed;left:0;right:0;bottom:0;background:#0e0e17;border-top:1px solid var(--line);padding:13px 20px;display:flex;align-items:center;gap:16px;justify-content:center;flex-wrap:wrap}
.barra strong{color:var(--gold)}
.perigo{color:#ff9aa8;font-weight:600}
.seguro{color:var(--green);font-weight:600}
.post.jafoi{opacity:.55;border-color:#2a2a3a}
.post.jafoi .arte img{filter:grayscale(.5)}
.nota.jafoi{background:#101a14;border-left-color:var(--green);color:#8fd8a8;font-weight:600}
.exportar{background:linear-gradient(135deg,var(--gold),#b8902f);color:#1a1206}
@media(max-width:820px){.post{flex-direction:column}.arte img{width:100%}}
</style>
</head>
<body>
<header>
  <h1>Programação do mês · {{ARROBA}}</h1>
  <p class="sub">
    {{TOTAL}} posts · {{PERIODO}} · 4 por semana · Instagram + Facebook<br>
    <strong>terça 6h</strong> reflexão · <strong>quinta 17h</strong> reel das 12 Tribos ·
    <strong>sábado 11h</strong> evento · <strong>domingo 17h</strong> evento
  </p>
  <div class="resumo">
    {{CHIPS}}
  </div>
  <div class="filtros">
    <button class="filtro ativo" data-filtro="pendentes">Falta decidir</button>
    <button class="filtro" data-filtro="todos">Ver todos</button>
    <button class="filtro" data-filtro="publicados">Só os publicados</button>
  </div>
</header>

<div class="chaveboxe">
  <div style="display:flex;align-items:center;gap:9px">
    <strong style="font-size:13.5px">Reescrita pela IA</strong>
    <span class="aichip"><span class="aidot off" id="aidot"></span>
      <span id="aistat">chave não configurada</span></span>
  </div>
  <p class="aviso" style="margin-top:6px">
    Cole sua chave da Anthropic para o botão “Enviar e reescrever” funcionar.
    Ela fica salva só neste navegador, nunca sai daqui.
    <a href="https://console.anthropic.com/settings/keys" target="_blank">Pegar a chave</a>
  </p>
  <input id="aikey" type="password" placeholder="sk-ant-…">
  <div class="textos">
    <button id="salvarchave">Salvar chave</button>
    <button id="removerchave">Remover</button>
  </div>
</div>

<div class="comando">
  <label>Peça o que quiser — em português mesmo</label>
  <textarea id="pedido" rows="3" placeholder="Exemplos:
· deixa o post 7 mais curto e mais celebrativo
· troca o versículo do post 12, esse já usamos muito
· muda o post 9 para sábado às 11h
· aprova todos os cards de reflexão
· cria 3 posts sobre a história do Arco Real"></textarea>
  <div class="textos">
    <button id="mandar" disabled>✨ Enviar</button>
    <button id="limparpedido">Limpar</button>
  </div>
  <div id="resposta" class="resposta hidden"></div>
</div>

{{CARTOES}}

<div class="barra">
  <span id="placar">—</span>
  <button class="exportar" id="aprovartodos">✅ Aprovar todos os que faltam</button>
  <button class="edit" id="exportar">⬇ Reenviar fila (se algo travou)</button>
  <button class="edit" id="limpar">↺ Zerar decisões</button>
</div>

<script>
const CHAVE = '{{CHAVE}}_aprovacao_v1';
const estado = JSON.parse(localStorage.getItem(CHAVE) || '{}');

/* ---------- chave da IA ---------- */
const CHAVE_API = '{{CHAVE}}_api_key';
const pegarChave = () => localStorage.getItem(CHAVE_API) || '';
function pintarStatus(){
  const tem = !!pegarChave();
  document.getElementById('aidot').className = 'aidot ' + (tem ? 'on' : 'off');
  document.getElementById('aistat').textContent = tem ? 'pronta' : 'chave não configurada';
  document.querySelectorAll('.enviar').forEach(b => b.disabled = !tem);
  const m = document.getElementById('mandar');
  if(m) m.disabled = !tem;
}
document.getElementById('salvarchave').onclick = () => {
  const k = document.getElementById('aikey').value.trim();
  if(!k) return;
  localStorage.setItem(CHAVE_API, k);
  document.getElementById('aikey').value = '';
  pintarStatus();
};
document.getElementById('removerchave').onclick = () => {
  localStorage.removeItem(CHAVE_API); pintarStatus();
};

/* As regras invioláveis viajam junto em toda reescrita. */
const SISTEMA = `Você é o redator do {{ARROBA}} — {{NOME_OFICIAL}}.

REGRAS INVIOLÁVEIS:
{{REGRAS}}

Responda APENAS a legenda final. Sem explicação, sem markdown, sem aspas em volta.`;

async function reescrever(legenda, pedido){
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': pegarChave(),
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
      'anthropic-dangerous-direct-browser-access': 'true'
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 600,
      system: SISTEMA,
      messages: [{ role: 'user', content:
        `LEGENDA ATUAL:\n${legenda}\n\nO QUE MUDAR:\n${pedido}\n\n` +
        `Reescreva a legenda inteira aplicando o pedido e respeitando todas as regras.` }]
    })
  });
  if(!r.ok){
    const e = await r.json().catch(() => ({}));
    throw new Error((e.error && e.error.message) || ('HTTP ' + r.status));
  }
  const j = await r.json();
  return (j.content?.[0]?.text || '').trim();
}

/* Decisões vivem no localStorage — limpar o navegador apaga tudo. O único
   lugar durável é o aprovado.json exportado. Daí este aviso insistente. */
const CHAVE_EXPORT = '{{CHAVE}}_exportado_em';
let mudouDesdeExport = false;

/* Salvar = guardar no navegador E mandar para a fila. O navegador não escreve
   em arquivo do projeto, então ele baixa o aprovado.json e o vigia.py (rodando
   em segundo plano) recolhe e envia ao GitHub sozinho. Aprovar basta. */
let timerFila = null;

function salvar(){
  localStorage.setItem(CHAVE, JSON.stringify(estado));
  mudouDesdeExport = true;
  placar();
  clearTimeout(timerFila);
  timerFila = setTimeout(enviarParaFila, 2500);   // espera parar de clicar
}

function enviarParaFila(){
  if(!Object.keys(estado).length) return;
  const dados = { exportado_em: new Date().toISOString(), posts: estado,
                  pedidos: pedidosPendentes };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(dados, null, 2)],
                                        {type:'application/json'}));
  a.download = 'aprovado.json';
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  localStorage.setItem(CHAVE_EXPORT, new Date().toLocaleString('pt-BR'));
  mudouDesdeExport = false;
  placar();
}

window.addEventListener('beforeunload', (e) => {
  const decisoes = Object.keys(estado).length;
  if(decisoes && mudouDesdeExport){ e.preventDefault(); e.returnValue = ''; }
});

function placar(){
  const posts = [...document.querySelectorAll('.post')];
  const ok = posts.filter(p => estado[p.dataset.id]?.decisao === 'aprovado').length;
  const aj = posts.filter(p => estado[p.dataset.id]?.decisao === 'ajustar').length;
  const quando = localStorage.getItem(CHAVE_EXPORT);
  let backup;
  if(!Object.keys(estado).length){
    backup = '';
  } else if(mudouDesdeExport){
    backup = ` · <span class="perigo">⚠️ não exportado — se limpar o ` +
             `navegador, você perde estas decisões</span>`;
  } else {
    backup = ` · <span class="seguro">✔ exportado ${quando}</span>`;
  }
  document.getElementById('placar').innerHTML =
    `<strong>${ok}</strong> aprovados · <strong>${aj}</strong> para ajustar · ` +
    `<strong>${posts.length - ok - aj}</strong> sem resposta${backup}`;
}

/* Copiar texto mesmo com a página aberta como arquivo local (file://), onde o
   navegador bloqueia a cópia automática. Cria um campo temporário, seleciona e
   copia — funciona offline. */
function copiarTexto(texto){
  const ta = document.createElement('textarea');
  ta.value = texto;
  ta.style.position = 'fixed'; ta.style.top = '0'; ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus(); ta.select(); ta.setSelectionRange(0, texto.length);
  let ok = false;
  try { ok = document.execCommand('copy'); } catch(e) {}
  document.body.removeChild(ta);
  if(!ok && navigator.clipboard){ navigator.clipboard.writeText(texto).catch(()=>{}); ok = true; }
  return ok;
}

/* Baixar direto pra pasta Downloads a partir da imagem já embutida (base64),
   sem abrir o navegador nem precisar clicar com o botão direito. */
function baixarDataURL(dataUrl, filename){
  fetch(dataUrl).then(r => r.blob()).then(blob => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  });
}

document.querySelectorAll('.post').forEach(post => { try {
  const id = post.dataset.id;
  const cap = post.querySelector('.cap');
  const obs = post.querySelector('.obs');

  const jafoi = !!post.dataset.jafoi;   // já publicado: sem aprovar/ajustar
  const estadoEl = post.querySelector('.estado');
  const conta = post.querySelector('.conta');

  function contar(){
    // conta só o corpo: tira o versículo e as hashtags
    const corpo = cap.value.split('\\n\\n')[0] || '';
    conta.textContent = `corpo: ${corpo.length}/200 caracteres`;
    conta.classList.toggle('longa', corpo.length > 200);
  }

  function pintar(){
    const e = estado[id];
    post.classList.remove('aprovado','ajustar');
    if(!e){ estadoEl.textContent=''; return; }
    post.classList.add(e.decisao);
    estadoEl.textContent = e.decisao === 'aprovado'
      ? '✅ Aprovado — já está na fila de publicação'
      : '✏️ Marcado para ajuste';
    estadoEl.style.color = e.decisao === 'aprovado' ? 'var(--green)' : 'var(--gold)';
    if(e.decisao === 'ajustar') post.querySelector('.obsbox')?.classList.remove('hidden');
  }

  // restaura o que já estava salvo
  if(estado[id]?.legenda) cap.value = estado[id].legenda;
  if(estado[id]?.obs && obs) obs.value = estado[id].obs;
  contar(); pintar();

  cap.oninput = () => { contar(); if(estado[id]) { estado[id].legenda = cap.value; salvar(); } };
  if(obs) obs.oninput = () => { if(estado[id]) { estado[id].obs = obs.value; salvar(); } };

  const numero = post.querySelector('.numero').textContent.replace(/\\s+/g,'');

  post.querySelector('.copiar').onclick = (e) => {
    const ok = copiarTexto(cap.value);
    const b = e.target; const antes = b.textContent;
    b.textContent = ok ? '✅ Copiado!' : '⚠️ Selecione e Cmd+C';
    setTimeout(() => b.textContent = antes, 1800);
  };

  post.querySelector('.baixartxt').onclick = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([cap.value], {type:'text/plain;charset=utf-8'}));
    a.download = `${numero}-${id}.txt`;
    document.body.appendChild(a); a.click(); a.remove();
  };

  // post já publicado não tem esses botões — some com eles sem quebrar o resto
  if(jafoi){
    post.querySelector('.acoes')?.remove();
    post.querySelector('.obsbox')?.remove();
  } else {
    const caixa = post.querySelector('.obsbox');
    post.querySelector('.ok').onclick = () => {
      estado[id] = { decisao:'aprovado', legenda: cap.value, obs:'' };
      caixa.classList.add('hidden'); salvar(); pintar();
    };
    post.querySelector('.edit').onclick = () => {
      estado[id] = { decisao:'ajustar', legenda: cap.value, obs: obs.value };
      caixa.classList.remove('hidden'); obs.focus(); salvar(); pintar();
    };
  }

  /* --- galeria + download direto pra Downloads --- */
  const slides = [...post.querySelectorAll('.slide')];
  let atual = 0;
  if(slides.length > 1){
    const cont = post.querySelector('.cont');
    const ir = n => {
      atual = (n + slides.length) % slides.length;
      slides.forEach((s, k) => s.classList.toggle('atual', k === atual));
      cont.textContent = `${atual + 1} / ${slides.length}`;
    };
    post.querySelector('.ant').onclick = () => ir(atual - 1);
    post.querySelector('.prox').onclick = () => ir(atual + 1);

    post.querySelector('.todas').onclick = async () => {
      for(const s of slides){
        baixarDataURL(s.src, s.dataset.baixar);
        await new Promise(r => setTimeout(r, 500));
      }
    };
    post.querySelector('.atual-baixar').onclick = () =>
      baixarDataURL(slides[atual].src, slides[atual].dataset.baixar);
  } else {
    post.querySelector('.unica').onclick = () =>
      baixarDataURL(slides[0].src, slides[0].dataset.baixar);
  }

  /* --- reescrita pela IA --- */
  const enviar = post.querySelector('.enviar');
  const desfazer = post.querySelector('.desfazer');
  let anterior = null;
  if(!enviar) return;   // post já publicado: não tem caixa de reescrita

  enviar.onclick = async () => {
    const pedido = obs.value.trim();
    if(!pedido){ obs.focus(); return; }
    anterior = cap.value;
    const rotulo = enviar.textContent;
    enviar.disabled = true; enviar.textContent = '✨ Reescrevendo…';
    try {
      const nova = await reescrever(cap.value, pedido);
      if(!nova) throw new Error('a IA devolveu vazio');
      cap.value = nova;
      contar();
      estado[id] = { decisao:'ajustar', legenda: nova, obs: pedido };
      salvar(); pintar();
      desfazer.disabled = false;
      estadoEl.textContent = '✨ Reescrito. Confira e aprove se ficou bom.';
      estadoEl.style.color = 'var(--gold)';
    } catch(e){
      estadoEl.textContent = '❌ ' + e.message;
      estadoEl.style.color = 'var(--red)';
    }
    enviar.disabled = false; enviar.textContent = rotulo;
  };

  desfazer.onclick = () => {
    if(anterior === null) return;
    cap.value = anterior; anterior = null;
    contar();
    if(estado[id]) { estado[id].legenda = cap.value; salvar(); }
    desfazer.disabled = true;
    estadoEl.textContent = '↺ Legenda anterior restaurada.';
  };
} catch(err) {
  // um post com problema não pode derrubar o painel inteiro
  console.error('post', post.dataset.id, err);
} });

/* --- filtros: por padrão o painel abre mostrando só o que falta decidir --- */
function aplicarFiltro(qual){
  document.querySelectorAll('.post').forEach(p => {
    const publicado = !!p.dataset.jafoi;
    const mostrar = qual === 'todos'
                 || (qual === 'publicados' && publicado)
                 || (qual === 'pendentes' && !publicado);
    p.classList.toggle('oculto', !mostrar);
  });
  document.querySelectorAll('.filtro').forEach(b =>
    b.classList.toggle('ativo', b.dataset.filtro === qual));
  localStorage.setItem('{{CHAVE}}_filtro', qual);
}
document.querySelectorAll('.filtro').forEach(b =>
  b.onclick = () => aplicarFiltro(b.dataset.filtro));
aplicarFiltro(localStorage.getItem('{{CHAVE}}_filtro') || 'pendentes');

pintarStatus();

/* =====================================================================
   CAIXA DE COMANDO — pede em português, a IA devolve ações estruturadas.

   O painel é uma página local: ele consegue reescrever textos, remarcar
   horários e aprovar em lote sozinho. O que precisa de imagem nova (criar
   post, trocar foto) ele registra como pedido e vai junto no aprovado.json
   para eu executar aqui. Nada é inventado como se tivesse sido feito.
   ===================================================================== */

const pedidosPendentes = JSON.parse(localStorage.getItem('{{CHAVE}}_pedidos') || '[]');

function contextoDoPlano(){
  return [...document.querySelectorAll('.post')].map(p => ({
    numero: p.dataset.numero,
    id: p.dataset.id,
    tipo: p.querySelector('.tag').textContent.trim(),
    quando: p.querySelector('.quando').textContent.trim(),
    publicado: !!p.dataset.jafoi,
    decisao: estado[p.dataset.id]?.decisao || 'sem resposta',
    legenda: p.querySelector('.cap').value
  }));
}

const SISTEMA_COMANDO = `Você é o assistente do painel de posts do {{ARROBA}} —
{{NOME_OFICIAL}}.

O Luiz pede em português. Você responde SOMENTE com um objeto JSON válido:

{
  "resposta": "explicação curta e direta, em português, do que você fez",
  "acoes": [
    {"tipo":"reescrever","numero":"POST 07","legenda":"legenda nova completa"},
    {"tipo":"horario","numero":"POST 09","quando":"2026-08-08 11:00"},
    {"tipo":"aprovar","numero":"POST 03"},
    {"tipo":"ajustar","numero":"POST 05","observacao":"o que mudar"},
    {"tipo":"pedido","descricao":"o que precisa de imagem nova ou código"}
  ]
}

REGRAS DAS LEGENDAS (invioláveis):
{{REGRAS}}
Nenhum versículo se repete entre posts.

REGRAS DAS AÇÕES:
· Post marcado "publicado": NÃO altere. Diga que já foi ao ar.
· Criar posts novos, trocar foto, mudar arte ou gerar reel → use "pedido".
  Você NÃO consegue gerar imagem. Seja honesto sobre isso na resposta.
· Se o pedido for ambíguo, devolva "acoes": [] e pergunte na "resposta".
· Só JSON. Sem markdown, sem crase, sem texto fora do objeto.`;

async function pedirIA(texto){
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': pegarChave(),
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
      'anthropic-dangerous-direct-browser-access': 'true'
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-5-20250929',
      max_tokens: 3000,
      system: SISTEMA_COMANDO,
      messages: [{ role:'user', content:
        `POSTS NO PAINEL:\n${JSON.stringify(contextoDoPlano(), null, 1)}\n\n` +
        `PEDIDO DO LUIZ:\n${texto}` }]
    })
  });
  if(!r.ok){
    const e = await r.json().catch(() => ({}));
    throw new Error((e.error && e.error.message) || ('HTTP ' + r.status));
  }
  const j = await r.json();
  let bruto = (j.content?.[0]?.text || '').trim()
    .replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
  try { return JSON.parse(bruto); }
  catch { throw new Error('a IA respondeu fora do formato: ' + bruto.slice(0, 200)); }
}

function acharPost(numero){
  const alvo = String(numero).toUpperCase().replace(/\s+/g,'');
  return [...document.querySelectorAll('.post')]
    .find(p => p.dataset.numero.replace(/\s+/g,'') === alvo);
}

function aplicarAcoes(acoes){
  const feitos = [], pendentes = [];
  for(const a of acoes || []){
    if(a.tipo === 'pedido'){
      pedidosPendentes.push({ descricao: a.descricao, em: new Date().toISOString() });
      pendentes.push('📋 ' + a.descricao);
      continue;
    }
    const post = acharPost(a.numero);
    if(!post){ pendentes.push('⚠️ não achei ' + a.numero); continue; }
    if(post.dataset.jafoi){ pendentes.push('🔒 ' + a.numero + ' já foi publicado'); continue; }

    const id = post.dataset.id;
    const cap = post.querySelector('.cap');

    if(a.tipo === 'reescrever' && a.legenda){
      cap.value = a.legenda;
      cap.dispatchEvent(new Event('input'));
      estado[id] = { ...(estado[id]||{}), decisao: estado[id]?.decisao || 'ajustar',
                     legenda: a.legenda };
      feitos.push('✏️ ' + a.numero + ' reescrito');
    }
    else if(a.tipo === 'horario' && a.quando){
      estado[id] = { ...(estado[id]||{}), legenda: cap.value, novo_horario: a.quando };
      post.querySelector('.quando').textContent += `  →  ${a.quando}`;
      feitos.push('🕐 ' + a.numero + ' remarcado para ' + a.quando);
    }
    else if(a.tipo === 'aprovar'){
      estado[id] = { decisao:'aprovado', legenda: cap.value, obs:'' };
      feitos.push('✅ ' + a.numero + ' aprovado');
    }
    else if(a.tipo === 'ajustar'){
      estado[id] = { decisao:'ajustar', legenda: cap.value, obs: a.observacao || '' };
      feitos.push('✏️ ' + a.numero + ' marcado para ajuste');
    }
    post.classList.add('mudou');
  }
  localStorage.setItem('{{CHAVE}}_pedidos', JSON.stringify(pedidosPendentes));
  salvar();
  document.querySelectorAll('.post').forEach(p => {
    const e = estado[p.dataset.id];
    p.classList.remove('aprovado','ajustar');
    if(e?.decisao) p.classList.add(e.decisao);
  });
  return { feitos, pendentes };
}

const caixaPedido = document.getElementById('pedido');
const btMandar = document.getElementById('mandar');
const respostaEl = document.getElementById('resposta');

btMandar.onclick = async () => {
  const texto = caixaPedido.value.trim();
  if(!texto){ caixaPedido.focus(); return; }
  btMandar.disabled = true; btMandar.textContent = '✨ Pensando…';
  respostaEl.classList.remove('hidden','erro');
  respostaEl.textContent = 'Lendo os 18 posts e montando a resposta…';
  try {
    const j = await pedirIA(texto);
    const { feitos, pendentes } = aplicarAcoes(j.acoes);
    respostaEl.textContent = j.resposta || '(sem resposta)';
    if(feitos.length)
      respostaEl.insertAdjacentHTML('beforeend',
        '<span class="feito">' + feitos.join('<br>') + '</span>');
    if(pendentes.length)
      respostaEl.insertAdjacentHTML('beforeend',
        '<span class="pendente">Precisa de mim no código:<br>' +
        pendentes.join('<br>') + '<br><em>vai junto no aprovado.json</em></span>');
  } catch(e){
    respostaEl.classList.add('erro');
    respostaEl.textContent = '❌ ' + e.message;
  }
  btMandar.disabled = false; btMandar.textContent = '✨ Enviar';
};

caixaPedido.addEventListener('keydown', e => {
  if((e.metaKey || e.ctrlKey) && e.key === 'Enter') btMandar.click();
});
document.getElementById('limparpedido').onclick = () => {
  caixaPedido.value = '';
  respostaEl.classList.add('hidden');
};

document.getElementById('aprovartodos').onclick = () => {
  const alvos = [...document.querySelectorAll('.post')].filter(p => {
    if(p.dataset.jafoi) return false;
    if(estado[p.dataset.id]?.decisao === 'aprovado') return false;
    return true;
  });
  // reel sem vídeo falha na publicação — não aprova junto
  const semVideo = alvos.filter(p => p.dataset.semvideo === '1');
  const podem = alvos.filter(p => p.dataset.semvideo !== '1');

  if(!podem.length){
    alert(semVideo.length
      ? `Só faltam ${semVideo.length} reel(s), e eles ainda não têm vídeo.`
      : 'Tudo já está aprovado.');
    return;
  }
  let msg = `Aprovar ${podem.length} post(s) de uma vez?`;
  if(semVideo.length)
    msg += `\n\nVou PULAR ${semVideo.length} reel(s) sem vídeo — eles falhariam.`;
  if(!confirm(msg)) return;

  podem.forEach(p => {
    const id = p.dataset.id;
    estado[id] = { decisao:'aprovado', legenda: p.querySelector('.cap').value, obs:'' };
    p.classList.remove('ajustar'); p.classList.add('aprovado');
    const e = p.querySelector('.estado');
    e.textContent = '✅ Aprovado — já está na fila de publicação';
    e.style.color = 'var(--green)';
    p.querySelector('.obsbox')?.classList.add('hidden');
  });
  salvar();
  alert(`✅ ${podem.length} aprovado(s). O vigia envia em até 1 minuto.`
        + (semVideo.length ? `\n\n${semVideo.length} reel(s) ficaram de fora (sem vídeo).` : ''));
};

document.getElementById('exportar').onclick = () => {
  if(!Object.keys(estado).length){
    alert('Nenhuma decisão ainda. Aprove algum post primeiro.');
    return;
  }
  enviarParaFila();
  alert('Reenviado. O vigia recolhe em até 1 minuto.');
};

document.getElementById('limpar').onclick = () => {
  if(!confirm('Apagar todas as decisões?')) return;
  localStorage.removeItem(CHAVE); location.reload();
};

placar();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
