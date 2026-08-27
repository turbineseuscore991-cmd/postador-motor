"""
industrial.py — Estilo de arte para cliente técnico, não cerimonial.

O layout do Arco Real é de irmandade: logo pequeno centralizado, serifa
capitular, moldura ornamentada, foto encaixada num quadro. Trocar só a cor
disso produz meia marca de cada — foi o que aconteceu na primeira arte da
Lastrom.

Aqui a lógica é outra, porque o leitor é outro:

  · FOTO SANGRANDO até a borda. Quem julga o serviço quer ver a peça, não a
    moldura. Foto grande é o argumento
  · LOGO GRANDE no topo, alinhado à esquerda. Empresa técnica assina o
    trabalho; não é selo discreto
  · SANS-SERIF pesado. Serifa em post industrial soa a convite de casamento
  · ETIQUETA DE CANTO para ANTES/DEPOIS — vocabulário de laudo, não de arte
  · BARRA INFERIOR CHAPADA, sem degradê ornamental

Quem escolhe é `marca.ESTILO`. Sem declarar, cai no clássico do Arco Real.
"""
from PIL import Image, ImageDraw, ImageFilter, ImageOps

import marca

from . import render

W_PADRAO, H_PADRAO = 1080, 1350
ESCALA = 2       # menos que os 3 do clássico: aqui não há serifa fina

# Largura do logo, em fração da arte. Empresa técnica assina o trabalho —
# em 0.30 ficava discreto demais para quem quer ser lembrado pelo nome.
LOGO_PCT = 0.40


def _cobrir(img, w, h):
    """Preenche w×h cortando o excesso — foto sangrando, sem borda."""
    s = max(w / img.width, h / img.height)
    nova = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    return nova.crop(((nova.width - w) // 2, (nova.height - h) // 2,
                      (nova.width - w) // 2 + w, (nova.height - h) // 2 + h))


def gerar(foto, saida, etiqueta=None, titulo=None, lower=None,
          formato="4x5", cortar_topo=0.0, cortar_rodape=0.0):
    """Uma arte industrial. `etiqueta` é o selo de canto (ANTES, DEPOIS…)."""
    W, H = render.FORMATOS[formato]
    e = ESCALA
    w, h = W * e, H * e

    img = ImageOps.exif_transpose(Image.open(foto)).convert("RGB")
    if cortar_topo or cortar_rodape:
        img = img.crop((0, round(img.height * cortar_topo),
                        img.width, round(img.height * (1 - cortar_rodape))))
    tela = _cobrir(img, w, h)

    # Escurece só as pontas. O meio da foto — a peça — fica intocado: é ele
    # que vende. Véu uniforme apaga justamente o que interessa.
    veu = Image.new("L", (1, h))
    d = ImageDraw.Draw(veu)
    for y in range(h):
        t = y / h
        v = int(215 * max(0, 1 - t / 0.26) ** 1.5 +
                225 * max(0, (t - 0.66) / 0.34) ** 1.4)
        d.point((0, y), fill=min(235, v))
    veu = veu.resize((w, h))
    tela = Image.composite(Image.new("RGB", (w, h), (8, 14, 11)), tela, veu)

    dr = ImageDraw.Draw(tela, "RGBA")
    verde = getattr(marca, "COR", (26, 122, 74))
    m = round(w * 0.055)

    # --- barra de topo: um fio da cor da marca, largura inteira
    dr.rectangle([0, 0, w, round(h * 0.007)], fill=verde)

    # --- logo grande, à esquerda
    logo_h = 0
    logo = render.LOGO_PADRAO
    if logo.exists():
        lg = Image.open(logo).convert("RGBA")
        alvo = round(w * LOGO_PCT)
        lg = lg.resize((alvo, round(lg.height * alvo / lg.width)), Image.LANCZOS)
        tela.paste(lg, (m, round(h * 0.045)), lg)
        logo_h = lg.height

    # --- etiqueta de canto: ANTES / DEPOIS
    if etiqueta:
        f = render.montserrat(w * 0.052, "Black")
        tw = dr.textlength(etiqueta, font=f)
        pad = round(w * 0.022)
        bx, by = w - m - tw - pad * 2, round(h * 0.045)
        dr.rounded_rectangle([bx, by, w - m, by + f.size + pad * 1.4],
                             radius=round(w * 0.008), fill=verde)
        dr.text((bx + pad, by + pad * 0.6), etiqueta, font=f, fill=(255, 255, 255))

    # --- texto de baixo, alinhado à esquerda como ficha técnica
    y = h - m
    if lower:
        f2 = render.montserrat(w * 0.026, "Medium")
        for linha in reversed(list(lower)):
            y -= f2.size * 1.42
            dr.text((m + round(w * 0.017), y), linha, font=f2,
                    fill=(214, 226, 218))
        # fio vertical à esquerda do bloco, no lugar da moldura ornamentada
        dr.rectangle([m, y - round(h*0.004), m + round(w * 0.006),
                      h - m - round(h*0.004)], fill=verde)
        y -= round(h * 0.022)

    if titulo:
        f1 = render.montserrat(w * 0.062, "Black")
        y -= f1.size * 1.1
        dr.text((m, y), titulo.upper(), font=f1, fill=(255, 255, 255))

    # --- @ no rodapé direito
    fa = render.montserrat(w * 0.024, "SemiBold")
    a = marca.ARROBA
    dr.text((w - m - dr.textlength(a, font=fa), h - m - fa.size * 1.1),
            a, font=fa, fill=(196, 214, 202))

    final = tela.resize((W, H), Image.LANCZOS)
    saida.parent.mkdir(parents=True, exist_ok=True)
    final.save(saida, "JPEG", quality=97, subsampling=0)
    return saida


# ---------------------------------------------------------------------------
# Card: post sem foto
# ---------------------------------------------------------------------------
# MITO e PERGUNTA são formatos de TEXTO. Enfiar uma foto genérica embaixo de
# uma frase que se sustenta sozinha foi o que deixou a primeira leva de posts
# com cara de repetida — a foto não acrescentava, só ocupava.
#
# O card do motor (`render.gerar_card`) é de versículo: serifa capitular,
# aspas, régua ornamentada. Num feed industrial ele sai como convite de
# casamento no meio de um laudo. Este aqui fala a mesma língua do `gerar`:
# mesmo fio verde no topo, mesmo logo à esquerda, mesma barra de rodapé.

def gerar_card(saida, texto, etiqueta=None, lower=None, formato="4x5"):
    """Arte só de texto. `etiqueta` é o rótulo pequeno acima da frase."""
    W, H = render.FORMATOS[formato]
    e = ESCALA
    w, h = W * e, H * e

    verde = getattr(marca, "COR", (26, 122, 74))
    verde_claro = getattr(marca, "COR_CLARA", (108, 196, 148))

    # Fundo: preto esverdeado, mais claro no alto à esquerda. Preto chapado
    # atrás de texto branco vira banner de propaganda; o desvio de verde
    # amarra o card à marca sem competir com a leitura.
    tela = Image.new("RGB", (w, h), (9, 16, 13))
    grad = Image.new("L", (64, 64))
    gd = ImageDraw.Draw(grad)
    for y in range(64):
        for x in range(64):
            gd.point((x, y), fill=int(255 * max(0.0, 1 - ((x + y) / 128) ** 0.75)))
    grad = grad.resize((w, h), Image.BICUBIC)
    tela = Image.composite(Image.new("RGB", (w, h), (16, 41, 30)), tela, grad)

    # Vinheta: segura o olho no centro, mesmo papel do `_fundo_fotografico`
    vin = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vin).ellipse((-w * 0.30, -h * 0.18, w * 1.30, h * 1.18), fill=255)
    vin = vin.filter(ImageFilter.GaussianBlur(w * 0.14)).point(lambda v: 255 - v)
    escuro = Image.new("RGBA", (w, h), (0, 0, 0, 150))
    escuro.putalpha(Image.composite(escuro.getchannel("A"),
                                    Image.new("L", (w, h), 0), vin))
    tela.paste(escuro, (0, 0), escuro)

    dr = ImageDraw.Draw(tela, "RGBA")
    m = round(w * 0.055)

    dr.rectangle([0, 0, w, round(h * 0.007)], fill=verde)

    logo = render.LOGO_PADRAO
    if logo.exists():
        lg = Image.open(logo).convert("RGBA")
        alvo = round(w * LOGO_PCT)
        lg = lg.resize((alvo, round(lg.height * alvo / lg.width)), Image.LANCZOS)
        tela.paste(lg, (m, round(h * 0.045)), lg)

    # --- rodapé primeiro: a frase precisa saber onde parar de descer
    y_baixo = h - m
    fa = render.montserrat(w * 0.024, "SemiBold")
    y_baixo -= fa.size * 1.1
    dr.text((w - m - dr.textlength(marca.ARROBA, font=fa), y_baixo),
            marca.ARROBA, font=fa, fill=(196, 214, 202))

    if lower:
        f2 = render.montserrat(w * 0.026, "Medium")
        y = y_baixo - round(h * 0.012)
        topo_lower = y - f2.size * 1.42 * len(list(lower))
        yy = topo_lower
        for linha in lower:
            dr.text((m + round(w * 0.017), yy), linha, font=f2, fill=(214, 226, 218))
            yy += f2.size * 1.42
        dr.rectangle([m, topo_lower - round(h * 0.004),
                      m + round(w * 0.006), y - round(h * 0.004)], fill=verde)
        y_baixo = topo_lower - round(h * 0.030)

    # --- a frase: ocupa o espaço que sobrou, o maior corpo que couber
    topo = round(h * 0.045) + round(w * LOGO_PCT * 0.42) + round(h * 0.075)
    if etiqueta:
        fe = render.montserrat(w * 0.030, "Black")
        dr.text((m, topo), etiqueta.upper(), font=fe, fill=verde_claro)
        dr.rectangle([m, topo + fe.size * 1.75, m + round(w * 0.10),
                      topo + fe.size * 1.75 + round(h * 0.0035)], fill=verde)
        topo += fe.size * 1.75 + round(h * 0.030)

    limite = w - m * 2
    disp = y_baixo - topo
    # Começa GRANDE e encolhe até caber. Em 0.086 a frase curta do card de
    # MITO deixava um vazio no meio da arte — num feed, arte com buraco lê
    # como erro de montagem, não como respiro.
    tam = w * 0.108
    while tam > w * 0.030:
        f1 = render.montserrat(tam, "Black")
        linhas = _quebrar(dr, texto, f1, limite)
        if len(linhas) * tam * 1.18 <= disp:
            break
        tam *= 0.94
    f1 = render.montserrat(tam, "Black")
    linhas = _quebrar(dr, texto, f1, limite)

    y = topo + (disp - len(linhas) * tam * 1.18) * 0.32   # levemente acima do centro
    for linha in linhas:
        dr.text((m, y), linha, font=f1, fill=(255, 255, 255))
        y += tam * 1.18

    final = tela.resize((W, H), Image.LANCZOS)
    saida.parent.mkdir(parents=True, exist_ok=True)
    final.save(saida, "JPEG", quality=97, subsampling=0)
    return saida


def _quebrar(dr, texto, fonte, limite):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if dr.textlength(teste, font=fonte) <= limite or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas
