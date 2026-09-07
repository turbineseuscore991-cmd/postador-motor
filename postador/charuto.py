"""
charuto.py — Estilo de arte para clube de charuto.

O terceiro estilo do motor, e nasceu por eliminação. O clássico é do Arco
Real: serifa capitular, moldura ornamentada, vocabulário de irmandade. O
industrial é da Lastrom: foto sangrando, sans-serif pesado, etiqueta de laudo.
Nenhum dos dois serve a um clube de charuto — o primeiro soa a templo, o
segundo a relatório técnico.

O que manda aqui é a **anilha**: a faixa impressa que envolve todo charuto.
Ela é ouro sobre escuro, tem fio duplo, letra pequena espaçada e um selo no
meio. É o vocabulário visual que o leitor deste perfil já conhece de cor —
ele segura uma na mão todo dia.

Daí as decisões:

  · FOTO SANGRANDO, escurecida embaixo. O charuto é o assunto; moldura
    ornamentada roubaria a atenção da folha, da capa e do anel
  · FIO DUPLO DOURADO atravessando o terço inferior — a anilha
  · SELO DO CLUBE centralizado no topo, pequeno. Ele já é redondo e dourado:
    é o mesmo objeto gráfico da anilha, e repetir isso amarra a peça
  · CORMORANT GARAMOND nos títulos. Serifa fina e alta, de rótulo de charuto
    e de rótulo de destilado — não a capitular pesada do Arco Real
  · MONTSERRAT espaçado nas linhas de baixo, em caixa alta pequena, como a
    letra miúda de uma anilha ("HECHO A MANO", "HABANA, CUBA")
  · SEM VÉU UNIFORME. Charuto se fotografa em luz baixa; escurecer tudo
    mataria o pouco brilho que a capa tem

Quem escolhe é `marca.ESTILO = "charuto"`.
"""
from PIL import Image, ImageDraw, ImageFilter, ImageOps

import marca

from . import render

ESCALA = 2

# Selo pequeno: ele assina, não anuncia. Em clube, marca grande soa a loja.
SELO_PCT = 0.20


def _cobrir(img, w, h):
    """Preenche w×h cortando o excesso — foto sangrando, sem borda."""
    s = max(w / img.width, h / img.height)
    nova = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    return nova.crop(((nova.width - w) // 2, (nova.height - h) // 2,
                      (nova.width - w) // 2 + w, (nova.height - h) // 2 + h))


def _ouro(claro=False):
    if claro:
        return getattr(marca, "COR_CLARA", (232, 194, 128))
    return getattr(marca, "COR", (198, 148, 68))


def _texto_espacado(dr, xy, txt, fonte, cor, espaco, centro=True):
    """Letra espaçada, como a letra miúda de uma anilha."""
    larg = sum(dr.textlength(c, font=fonte) + espaco for c in txt) - espaco
    x, y = xy
    if centro:
        x -= larg / 2
    for c in txt:
        dr.text((x, y), c, font=fonte, fill=cor)
        x += dr.textlength(c, font=fonte) + espaco
    return larg


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


def _medir_bloco(dr, w, h, m, titulo, lower, etiqueta):
    """Altura em que o bloco inferior começa. Só mede; não desenha nada."""
    y = h - m
    y -= render.montserrat(w * 0.021, "Medium").size * 1.2      # @
    y -= round(h * 0.026)
    if lower:
        f2 = render.montserrat(w * 0.0225, "SemiBold")
        y -= f2.size * 1.62 * len(list(lower)) + round(h * 0.020)
    y -= round(h * 0.030)                                        # fio de baixo
    if titulo:
        limite = w - m * 2 - round(w * 0.02)
        tam = w * 0.072
        while tam > w * 0.032:
            if len(_quebrar(dr, titulo.upper(), render.cormorant(tam, "Bold"),
                            limite)) <= 2:
                break
            tam *= 0.93
        n = len(_quebrar(dr, titulo.upper(), render.cormorant(tam, "Bold"),
                         limite)[:2])
        y -= tam * 1.14 * n + round(h * 0.016)
    if etiqueta:
        y -= render.montserrat(w * 0.020, "Bold").size * 1.5 + round(h * 0.016)
    return max(0, y)


def gerar(foto, saida, titulo=None, lower=None, etiqueta=None,
          formato="4x5", cortar_topo=0.0, cortar_rodape=0.0, modo="sangrar"):
    """Uma arte de charuto. `etiqueta` é o rótulo pequeno acima do título.

    `modo`:
      "sangrar"  foto preenche a arte, cortando o que sobra. O padrão
      "conter"   foto INTEIRA, sobre o fundo escuro, com fio dourado em volta

    Quando usar "conter": foto de celular na vertical em que o assunto está
    nas duas pontas. A do Cohiba com a bandeira cubana é o caso exato —
    bandeira no alto, anilha embaixo, e qualquer corte 4:5 perde uma das
    duas. Sangrar é mais bonito quando cabe; quando não cabe, é mutilação.
    """
    W, H = render.FORMATOS[formato]
    e = ESCALA
    w, h = W * e, H * e
    ouro, ouro_claro = _ouro(), _ouro(True)

    img = ImageOps.exif_transpose(Image.open(foto)).convert("RGB")
    if cortar_topo or cortar_rodape:
        img = img.crop((0, round(img.height * cortar_topo),
                        img.width, round(img.height * (1 - cortar_rodape))))

    if modo == "conter":
        return _conter(img, saida, W, H, w, h, e, titulo, lower, etiqueta,
                       ouro, ouro_claro)

    tela = _cobrir(img, w, h)
    dr = ImageDraw.Draw(tela, "RGBA")
    m = round(w * 0.075)

    # Onde o bloco de texto COMEÇA — medido antes de escurecer.
    #
    # A primeira versão usava um degradê fixo (começando em 34% da altura), e
    # em foto de céu claro a primeira linha do título caía fora da parte
    # escura: ouro sobre nuvem, ilegível. O escurecimento tem de seguir o
    # texto, não um número escolhido no olho.
    topo_bloco = _medir_bloco(dr, w, h, m, titulo, lower, etiqueta)

    # A rampa TERMINA onde o texto começa — não começa ali. Escrevi ao
    # contrário na primeira tentativa e o título continuou sobre a parte
    # clara: quando o degradê ainda estava subindo, a serifa já tinha
    # chegado. Aqui, ao alcançar o bloco, o fundo já está escuro.
    fim = max(0.20, topo_bloco / h)
    ini = max(0.05, fim - 0.30)
    veu = Image.new("L", (1, h))
    d = ImageDraw.Draw(veu)
    for y in range(h):
        t = y / h
        rampa = min(1.0, max(0.0, (t - ini) / max(0.01, fim - ini)))
        v = int(228 * rampa ** 1.25          # escuro já no topo do bloco
                + 22 * min(1.0, max(0.0, (t - fim) / max(0.01, 1 - fim)))
                + 74 * max(0.0, 1 - t / 0.22) ** 2)
        d.point((0, y), fill=min(248, v))
    veu = veu.resize((w, h))
    tela = Image.composite(Image.new("RGB", (w, h), (10, 8, 6)), tela, veu)
    dr = ImageDraw.Draw(tela, "RGBA")

    _selo(tela, w, h)
    dr = ImageDraw.Draw(tela, "RGBA")
    _desenhar_bloco(tela, dr, w, h, m, titulo, lower, etiqueta, ouro, ouro_claro)

    final = tela.resize((W, H), Image.LANCZOS)
    saida.parent.mkdir(parents=True, exist_ok=True)
    final.save(saida, "JPEG", quality=97, subsampling=0)
    return saida


def _selo(tela, w, h, halo=True):
    """Selo do clube no topo. `halo` escurece atrás, para foto clara."""
    selo = render.LOGO_PADRAO
    if not selo.exists():
        return
    lg = Image.open(selo).convert("RGBA")
    alvo = round(w * SELO_PCT)
    lg = lg.resize((alvo, round(lg.height * alvo / lg.width)), Image.LANCZOS)
    if halo:
        # Sobre céu claro o traço dourado sumia. Um halo escuro e difuso,
        # do tamanho do selo, devolve o contraste sem virar caixa preta.
        cx, cy = w // 2, round(h * 0.052) + lg.height // 2
        r = alvo * 0.78
        mascara = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mascara).ellipse([cx - r, cy - r, cx + r, cy + r], fill=150)
        mascara = mascara.filter(ImageFilter.GaussianBlur(alvo * 0.28))
        tela.paste(Image.new("RGB", (w, h), (10, 8, 6)), (0, 0), mascara)
    sombra = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sombra.paste(lg, ((w - alvo) // 2, round(h * 0.052)), lg)
    sombra = sombra.filter(ImageFilter.GaussianBlur(w * 0.006))
    tela.paste(sombra, (0, 0), sombra)
    tela.paste(lg, ((w - alvo) // 2, round(h * 0.052)), lg)


def _desenhar_bloco(tela, dr, w, h, m, titulo, lower, etiqueta, ouro, ouro_claro):
    """A anilha: fio duplo com o texto entre os fios.

    Monta-se de baixo para cima, para o bloco encostar no rodapé certo.
    """
    y = h - m

    # @ do clube, na base
    fa = render.montserrat(w * 0.021, "Medium")
    y -= fa.size * 1.2
    _texto_espacado(dr, (w / 2, y), marca.ARROBA.upper(), fa,
                    (214, 200, 176, 235), w * 0.0035)
    y -= round(h * 0.026)

    # linhas de baixo, em caixa alta pequena e espaçada
    if lower:
        f2 = render.montserrat(w * 0.0225, "SemiBold")
        for linha in reversed(list(lower)):
            y -= f2.size * 1.62
            _texto_espacado(dr, (w / 2, y), linha.upper(), f2,
                            (236, 224, 202), w * 0.0032)
        y -= round(h * 0.020)

    # fio de baixo da anilha
    dr.rectangle([m, y, w - m, y + max(1, round(h * 0.0016))], fill=ouro)
    y -= round(h * 0.030)

    # título: serifa alta, ouro claro
    if titulo:
        limite = w - m * 2 - round(w * 0.02)
        tam = w * 0.072
        while tam > w * 0.032:
            f1 = render.cormorant(tam, "Bold")
            if len(_quebrar(dr, titulo.upper(), f1, limite)) <= 2:
                break
            tam *= 0.93
        f1 = render.cormorant(tam, "Bold")
        linhas = _quebrar(dr, titulo.upper(), f1, limite)[:2]
        # Sombra difusa sob a serifa. O degradê resolve o fundo médio; couro,
        # madeira e brasa continuam competindo com o ouro sem isto.
        camada = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dsom = ImageDraw.Draw(camada)
        yy = y
        for linha in reversed(linhas):
            yy -= tam * 1.14
            _texto_espacado(dsom, (w / 2, yy), linha, f1, (0, 0, 0, 205), w * 0.004)
        camada = camada.filter(ImageFilter.GaussianBlur(w * 0.008))
        tela.paste(camada, (0, 0), camada)
        dr = ImageDraw.Draw(tela, "RGBA")
        for linha in reversed(linhas):
            y -= tam * 1.14
            larg = _texto_espacado(dr, (w / 2, y), linha, f1, ouro_claro, w * 0.004)
        y -= round(h * 0.016)

    # etiqueta pequena acima do título — a "denominação" da anilha
    if etiqueta:
        fe = render.montserrat(w * 0.020, "Bold")
        y -= fe.size * 1.5
        _texto_espacado(dr, (w / 2, y), etiqueta.upper(), fe, ouro, w * 0.0085)
        y -= round(h * 0.016)

    # fio de cima da anilha, fechando o bloco
    dr.rectangle([m, y, w - m, y + max(1, round(h * 0.0016))], fill=ouro)
    return y


def gerar_card(saida, texto, etiqueta=None, lower=None, formato="4x5"):
    """Arte só de texto, para quando não houver foto que sustente o post."""
    W, H = render.FORMATOS[formato]
    e = ESCALA
    w, h = W * e, H * e
    ouro, ouro_claro = _ouro(), _ouro(True)

    # Fundo: marrom-tabaco muito escuro, mais quente no alto
    tela = Image.new("RGB", (w, h), (14, 10, 7))
    grad = Image.new("L", (64, 64))
    gd = ImageDraw.Draw(grad)
    for yy in range(64):
        for xx in range(64):
            gd.point((xx, yy), fill=int(255 * max(0.0, 1 - (yy / 64) ** 0.6)))
    tela = Image.composite(Image.new("RGB", (w, h), (44, 28, 16)), tela,
                           grad.resize((w, h), Image.BICUBIC))

    dr = ImageDraw.Draw(tela, "RGBA")
    m = round(w * 0.085)

    selo = render.LOGO_PADRAO
    if selo.exists():
        lg = Image.open(selo).convert("RGBA")
        alvo = round(w * SELO_PCT)
        lg = lg.resize((alvo, round(lg.height * alvo / lg.width)), Image.LANCZOS)
        tela.paste(lg, ((w - alvo) // 2, round(h * 0.075)), lg)

    y = h - m
    fa = render.montserrat(w * 0.021, "Medium")
    y -= fa.size * 1.2
    _texto_espacado(dr, (w / 2, y), marca.ARROBA.upper(), fa,
                    (214, 200, 176, 235), w * 0.0035)

    if lower:
        f2 = render.montserrat(w * 0.0225, "SemiBold")
        y -= round(h * 0.026)
        for linha in reversed(list(lower)):
            y -= f2.size * 1.62
            _texto_espacado(dr, (w / 2, y), linha.upper(), f2,
                            (236, 224, 202), w * 0.0032)

    topo = round(h * 0.075) + round(w * SELO_PCT) + round(h * 0.055)
    if etiqueta:
        fe = render.montserrat(w * 0.020, "Bold")
        _texto_espacado(dr, (w / 2, topo), etiqueta.upper(), fe, ouro, w * 0.0085)
        topo += fe.size * 1.5 + round(h * 0.012)
        dr.rectangle([w / 2 - w * 0.06, topo, w / 2 + w * 0.06,
                      topo + max(1, round(h * 0.0016))], fill=ouro)
        topo += round(h * 0.034)

    limite = w - m * 2
    disp = (y - round(h * 0.05)) - topo
    tam = w * 0.078
    while tam > w * 0.030:
        f1 = render.cormorant(tam, "Bold")
        linhas = _quebrar(dr, texto, f1, limite)
        if len(linhas) * tam * 1.24 <= disp:
            break
        tam *= 0.94
    f1 = render.cormorant(tam, "Bold")
    linhas = _quebrar(dr, texto, f1, limite)
    yy = topo + (disp - len(linhas) * tam * 1.24) * 0.30
    for linha in linhas:
        larg = dr.textlength(linha, font=f1)
        dr.text(((w - larg) / 2, yy), linha, font=f1, fill=(244, 236, 220))
        yy += tam * 1.24

    final = tela.resize((W, H), Image.LANCZOS)
    saida.parent.mkdir(parents=True, exist_ok=True)
    final.save(saida, "JPEG", quality=97, subsampling=0)
    return saida


def _conter(img, saida, W, H, w, h, e, titulo, lower, etiqueta, ouro, ouro_claro):
    """Foto inteira sobre o fundo da marca, com fio dourado em volta."""
    # Fundo: a própria foto, muito desfocada e escurecida. Combina de cor com
    # a imagem e nunca briga com o texto — o mesmo truque do estilo clássico.
    fundo = _cobrir(img, w, h).filter(ImageFilter.GaussianBlur(w * 0.045))
    fundo = Image.blend(fundo, Image.new("RGB", (w, h), (12, 9, 6)), 0.72)
    tela = fundo
    dr = ImageDraw.Draw(tela, "RGBA")
    m = round(w * 0.075)

    topo_bloco = _medir_bloco(dr, w, h, m, titulo, lower, etiqueta)

    # área livre entre o selo e o bloco de texto
    y_ini = round(h * 0.052) + round(w * SELO_PCT) + round(h * 0.030)
    disp_h = topo_bloco - y_ini - round(h * 0.028)
    disp_w = w - m * 2
    s = min(disp_w / img.width, disp_h / img.height)
    nw, nh = round(img.width * s), round(img.height * s)
    # `_medir_bloco` devolve float; sem arredondar aqui, o paste do Pillow
    # recusa a coordenada e a arte inteira falha
    x = int((w - nw) // 2)
    y = int(y_ini + (disp_h - nh) // 2)

    sombra = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rectangle([x, y + round(h * 0.006),
                                      x + nw, y + nh + round(h * 0.006)],
                                     fill=(0, 0, 0, 170))
    sombra = sombra.filter(ImageFilter.GaussianBlur(w * 0.016))
    tela.paste(sombra, (0, 0), sombra)
    tela.paste(img.resize((nw, nh), Image.LANCZOS), (x, y))

    # fio dourado fino em volta — a moldura da anilha
    dr = ImageDraw.Draw(tela, "RGBA")
    dr.rectangle([x, y, x + nw - 1, y + nh - 1],
                 outline=ouro + (215,), width=max(2, round(w * 0.0022)))

    _desenhar_bloco(tela, dr, w, h, m, titulo, lower, etiqueta, ouro, ouro_claro)
    _selo(tela, w, h, halo=False)

    final = tela.resize((W, H), Image.LANCZOS)
    saida.parent.mkdir(parents=True, exist_ok=True)
    final.save(saida, "JPEG", quality=97, subsampling=0)
    return saida
