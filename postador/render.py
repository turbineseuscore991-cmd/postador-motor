"""
render.py — Arte dos posts do Sagrado Arco Real, em alta fidelidade.

Mantém o layout do `gerador-posts-arcorealnewok.html` que o Luiz já aprovava à
mão, mas resolve o problema do texto "esbranquiçado":

  · SUPERSAMPLING — desenha tudo numa tela 3x maior e reduz com LANCZOS no
    final. É isso que dá borda limpa em serifa fina. Desenhar direto em 1080
    deixa o Cinzel lavado, não importa a fonte.

  · SOMBRA DIFUSA atrás de todo texto, para o dourado ter contraste contra
    céu claro ou mármore.

  · Sobre "4K": o Instagram entrega no máximo 1080 de largura no feed. Mandar
    4K não deixa mais nítido — a Meta reprocessa e piora. O certo é reduzir
    nós mesmos com LANCZOS e enviar 1080x1350. O master 4K fica guardado para
    reels, impressão e reuso.

Uso:
    render.gerar(foto=..., saida=..., titulo=..., lower=(nome, cargo))
    render.gerar_card(saida=..., versiculo=..., referencia=..., fundo=...)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

import marca   # do cliente

from .projeto import raiz

RAIZ = raiz()                                # a pasta do CLIENTE
MOTOR = Path(__file__).resolve().parent      # a pasta do MOTOR

# As fontes são do motor: Cinzel, Montserrat e Cormorant servem qualquer marca
# e não faz sentido cada cliente carregar a própria cópia.
FONTES = MOTOR / "assets" / "fontes"

# O logo é do CLIENTE. Se isto apontasse para o motor, a Lastrom sairia com o
# emblema do Arco Real — o erro mais caro que esta extração poderia introduzir,
# porque a arte fica bonita e ninguém percebe até estar publicada.
LOGO_PADRAO = RAIZ / "assets" / "img" / "logo_0.png"

FORMATOS = {"4x5": (1080, 1350), "1x1": (1080, 1080), "9x16": (1080, 1920)}

# As DUAS cores da arte, lidas do cliente.
#
#   COR         moldura da foto, títulos, régua sob o cabeçalho
#   COR_CLARA   a barra estreita ao lado do texto da faixa inferior
#
# Eram constantes globais aqui — ouro do Arco Real gravado no motor. Trocar
# para outro cliente exigiria mexer no motor e mudaria o Arco Real junto.
# Agora cada `marca.py` traz o seu par; sem declarar, cai no ouro de sempre,
# então nada muda para quem já roda.
#
# O ouro é mais saturado que o original: #d4af5a lavava contra fundo claro,
# e foi reclamação do Luiz.
OURO = getattr(marca, "COR", (222, 178, 72))
OURO_CLARO = getattr(marca, "COR_CLARA", (243, 208, 118))
ESCALA_PADRAO = 3


# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------

def _fonte(arquivo, variacao, tamanho):
    f = ImageFont.truetype(str(FONTES / arquivo), max(1, int(tamanho)))
    f.set_variation_by_name(variacao)
    return f


def montserrat(t, peso="SemiBold"):
    return _fonte("Montserrat.ttf", peso, t)


def cormorant(t, peso="Bold"):
    return _fonte("CormorantGaramond.ttf", peso, t)


def cinzel(t, peso="Black"):
    return _fonte("Cinzel.ttf", peso, t)


# ---------------------------------------------------------------------------
# Texto com sombra
# ---------------------------------------------------------------------------

class Tela:
    """Envolve a imagem e desenha texto sempre sobre uma sombra difusa, para o
    dourado nunca sumir contra céu claro."""

    def __init__(self, img):
        self.img = img
        self.d = ImageDraw.Draw(img)
        self.W, self.H = img.size

    def largura(self, texto, fonte):
        return self.d.textlength(texto, font=fonte)

    def texto(self, xy, txt, fonte, cor, anchor="la", sombra=0.006, forca=190):
        if sombra:
            raio = max(2, int(self.W * sombra))
            camada = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            ImageDraw.Draw(camada).text(xy, txt, font=fonte, fill=(0, 0, 0, forca),
                                        anchor=anchor)
            camada = camada.filter(ImageFilter.GaussianBlur(raio))
            self.img.paste(camada, (0, 0), camada)
        self.d.text(xy, txt, font=fonte, fill=cor, anchor=anchor)

    def texto_espacado(self, xy, txt, fonte, cor, espaco, sombra=0.005):
        larg = sum(self.largura(c, fonte) + espaco for c in txt) - espaco
        x, y = xy
        x -= larg / 2
        for c in txt:
            self.texto((x, y), c, fonte, cor, anchor="ls", sombra=sombra)
            x += self.largura(c, fonte) + espaco


# ---------------------------------------------------------------------------
# Degradês e máscaras
# ---------------------------------------------------------------------------

def _interp(paradas, t):
    if t <= paradas[0][0]:
        return paradas[0][1]
    if t >= paradas[-1][0]:
        return paradas[-1][1]
    for (p0, c0), (p1, c1) in zip(paradas, paradas[1:]):
        if p0 <= t <= p1:
            k = 0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(round(a + (b - a) * k) for a, b in zip(c0, c1))
    return paradas[-1][1]


# O degradê de fundo e o da faixa inferior também são do CLIENTE.
#
# Parametrizei só COR e COR_CLARA na primeira passada, e o resultado foi uma
# arte da Lastrom com título verde sobre o azul-marinho e o carmesim do Arco
# Real: metade de cada marca. Cor de traço não basta — o fundo é o que dá o
# caráter da peça.
FUNDO = getattr(marca, "FUNDO", [
    (0.00, (12, 19, 48)), (0.55, (10, 10, 24)), (1.00, (5, 5, 12))])

# A faixa que carrega o nome do Capítulo, com transparência no fim de cada cor.
FAIXA = getattr(marca, "FAIXA", [
    (0.00, (22, 34, 88, 247)),
    (0.52, (100, 20, 60, 240)),
    (1.00, (168, 22, 52, 224)),
])


def _degrade_diagonal(w, h, paradas):
    pw = ph = 64
    pequeno = Image.new("RGB", (pw, ph))
    px = pequeno.load()
    denom = pw * pw + ph * ph
    for y in range(ph):
        for x in range(pw):
            px[x, y] = _interp(paradas, (x * pw + y * ph) / denom)
    return pequeno.resize((w, h), Image.BICUBIC)


def _degrade_vertical(w, h, paradas):
    faixa = Image.new("RGBA", (1, h))
    px = faixa.load()
    for y in range(h):
        px[0, y] = _interp(paradas, y / max(1, h - 1))
    return faixa.resize((w, h))


def _degrade_horizontal(w, h, paradas):
    faixa = Image.new("RGBA", (w, 1))
    px = faixa.load()
    for x in range(w):
        px[x, 0] = _interp(paradas, x / max(1, w - 1))
    return faixa.resize((w, h))


def _mascara(w, h, raio):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=raio, fill=255)
    return m


# ---------------------------------------------------------------------------
# Camadas
# ---------------------------------------------------------------------------

def _foto(tela, foto, modo="contain", area=None, cortar_rodape=0.0, cortar_topo=0.0):
    """Fotos de grupo costumam ter teto e chão vazios. Cortar essas faixas faz
    os Companheiros ocuparem a moldura inteira em vez de ficarem pequenos."""
    W, H = tela.W, tela.H
    img = ImageOps.exif_transpose(Image.open(foto)).convert("RGB")
    if cortar_topo or cortar_rodape:
        img = img.crop((0, round(img.height * cortar_topo),
                        img.width, round(img.height * (1 - cortar_rodape))))
    iw, ih = img.size

    if modo == "cover":
        s = max(W / iw, H / ih)
        nw, nh = round(iw * s), round(ih * s)
        tela.img.paste(img.resize((nw, nh), Image.LANCZOS), ((W - nw) // 2, (H - nh) // 2))
        return

    pad = W * 0.055
    topo, fundo = area if area else (pad, H - pad)
    disp = fundo - topo
    s = min((W - pad * 2) / iw, disp / ih)
    nw, nh = round(iw * s), round(ih * s)
    x, y = (W - nw) // 2, round(topo + (disp - nh) / 2)
    raio = round(W * 0.017)
    mask = _mascara(nw, nh, raio)

    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bloco = Image.new("RGBA", (nw, nh), (0, 0, 0, 150))
    bloco.putalpha(mask.point(lambda v: v * 150 // 255))
    sombra.paste(bloco, (x, round(y + H * 0.011)), bloco)
    sombra = sombra.filter(ImageFilter.GaussianBlur(W * 0.019))
    tela.img.paste(sombra, (0, 0), sombra)

    tela.img.paste(img.resize((nw, nh), Image.LANCZOS), (x, y), mask)

    borda = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(borda).rounded_rectangle(
        (x, y, x + nw - 1, y + nh - 1), radius=raio,
        outline=OURO + (150,), width=max(2, round(W * 0.0028)))
    tela.img.paste(borda, (0, 0), borda)


def _veu_inferior(tela):
    W, H = tela.W, tela.H
    topo = round(H * 0.62)
    veu = _degrade_vertical(W, H - topo, [(0.0, (0, 0, 0, 0)), (1.0, (0, 0, 0, 128))])
    tela.img.paste(veu, (0, topo), veu)


def _logo(tela, caminho, pct=17, pos="tc"):
    """Padrão `tc` = topo centralizado. É a âncora visual da marca — o mesmo
    lugar em todo post, foto ou card."""
    W, H = tela.W, tela.H
    logo = Image.open(caminho).convert("RGBA")
    lw = round(W * pct / 100)
    lh = round(lw / (logo.width / logo.height))
    m = W * 0.045
    if pos == "tc":
        bx, by = (W - lw) / 2, m
    elif pos == "bc":
        bx, by = (W - lw) / 2, H - m - lh
    else:
        bx = m if pos in ("tl", "bl") else W - m - lw
        by = m if pos in ("tl", "tr") else H - m - lh
    lg = logo.resize((lw, lh), Image.LANCZOS)
    tela.img.paste(lg, (round(bx), round(by)), lg)


def _altura_logo(caminho, W, pct):
    lg = Image.open(caminho)
    return (W * pct / 100) / (lg.width / lg.height)


def _arroba(tela, texto=None):
    texto = texto or marca.ARROBA
    """Canto inferior direito. O logo centralizado no topo é a âncora da marca;
    o @ fica discreto no canto, como assinatura."""
    W, H = tela.W, tela.H
    tela.texto((W - W * 0.045, H - W * 0.032), texto,
               montserrat(W * 0.026), (255, 255, 255, 225), anchor="rs")


def _quebrar(tela, texto, fonte, limite):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if tela.largura(teste, fonte) <= limite or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _titulo(tela, titulo, y_topo, desenhar=True):
    """Cinzel Black, grande. Devolve onde o conteúdo seguinte pode começar."""
    if not titulo:
        return y_topo
    W = tela.W
    texto = titulo.upper()
    limite = W * 0.86

    tam = W * 0.058
    while tam > W * 0.030:
        if len(_quebrar(tela, texto, cinzel(tam), limite)) <= 2:
            break
        tam *= 0.92
    fonte = cinzel(tam)
    linhas = _quebrar(tela, texto, fonte, limite)[:2]

    y = y_topo
    for linha in linhas:
        if desenhar:
            tela.texto((W / 2, y), linha, fonte, OURO, anchor="ma", sombra=0.008, forca=215)
        y += tam * 1.26
    return y


def _lower(tela, nome, cargo, alt_pct=13, margem_pct=4, margem_baixo=None):
    """`margem_baixo` sobe a faixa para o @ do rodapé não encavalar nela."""
    if not (nome or cargo):
        return
    W, H = tela.W, tela.H
    barH = round(H * alt_pct / 100)
    mx = round(W * margem_pct / 100)
    bw = W - mx * 2
    x, y = mx, round(H - barH - (margem_baixo if margem_baixo is not None else mx))

    faixa = _degrade_horizontal(bw, barH, FAIXA)
    faixa.putalpha(Image.composite(faixa.getchannel("A"),
                                   Image.new("L", (bw, barH), 0),
                                   _mascara(bw, barH, round(W * 0.012))))
    tela.img.paste(faixa, (x, y), faixa)

    tela.d.rectangle((x, y + barH * 0.15,
                      x + round(W * 0.0065), y + barH * 0.85), fill=OURO_CLARO)

    recuo = x + round(W * 0.024)
    limite = bw - round(W * 0.055)
    if nome:
        tam = barH * 0.37
        while tam > barH * 0.20 and tela.largura(nome, cormorant(tam)) > limite:
            tam *= 0.95
        tela.texto((recuo, y + barH * 0.48), nome, cormorant(tam),
                   (255, 255, 255), anchor="ls", sombra=0.004)
    if cargo:
        tam = barH * 0.175
        alvo = cargo.upper()
        while tam > barH * 0.10 and tela.largura(alvo, montserrat(tam)) > limite:
            tam *= 0.95
        tela.texto((recuo, y + barH * 0.77), alvo, montserrat(tam),
                   (243, 214, 140), anchor="ls", sombra=0.003)


def _fundo_fotografico(tela, caminho, escurecer=0.62, desfoque=0.004):
    """Foto de céu, cachoeira, águia… atrás do texto. Recebe névoa, escurecimento
    e vinheta — sem isso o versículo some na imagem."""
    W, H = tela.W, tela.H
    img = ImageOps.exif_transpose(Image.open(caminho)).convert("RGB")
    s = max(W / img.width, H / img.height)
    nw, nh = round(img.width * s), round(img.height * s)
    img = img.resize((nw, nh), Image.LANCZOS).crop(
        ((nw - W) // 2, (nh - H) // 2, (nw - W) // 2 + W, (nh - H) // 2 + H))
    if desfoque:
        img = img.filter(ImageFilter.GaussianBlur(W * desfoque))
    tela.img.paste(img, (0, 0))

    # névoa escura por cima
    veu = Image.new("RGBA", (W, H), (6, 8, 20, round(255 * escurecer)))
    tela.img.paste(veu, (0, 0), veu)

    # vinheta: escurece as bordas e segura o olho no centro
    vin = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vin).ellipse(
        (-W * 0.35, -H * 0.22, W * 1.35, H * 1.22), fill=255)
    vin = vin.filter(ImageFilter.GaussianBlur(W * 0.16)).point(lambda v: 255 - v)
    escuro = Image.new("RGBA", (W, H), (0, 0, 0, 165))
    escuro.putalpha(Image.composite(escuro.getchannel("A"),
                                    Image.new("L", (W, H), 0), vin))
    tela.img.paste(escuro, (0, 0), escuro)


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------

def _salvar(img, saida, alvo, master=None, qualidade=97):
    """qualidade 97 + subsampling 0 (sem subamostragem de cor). O ouro sobre
    fundo escuro é justamente onde o JPEG padrão suja primeiro."""
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    if master:
        Path(master).parent.mkdir(parents=True, exist_ok=True)
        img.save(master, "JPEG", quality=97, subsampling=0, optimize=True)
    img.resize(alvo, Image.LANCZOS).save(
        saida, "JPEG", quality=qualidade, subsampling=0, optimize=True)
    return saida


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def gerar(foto, saida, formato="4x5", modo="contain", titulo=None, lower=None,
          logo=None, mostrar_logo=True, mostrar_arroba=True,
          arroba=None, logo_pct=17, logo_pos="tc",
          cortar_rodape=0.0, cortar_topo=0.0, escala=ESCALA_PADRAO,
          master=None, fundo_proprio=True):
    alvo = FORMATOS[formato]
    W, H = alvo[0] * escala, alvo[1] * escala

    tela = Tela(_degrade_diagonal(W, H, FUNDO).convert("RGB"))

    # A própria foto, muito desfocada e escurecida, preenche o vazio atrás da
    # moldura. Sempre combina de cor com a foto e nunca briga com o texto.
    if foto and modo == "contain" and fundo_proprio:
        _fundo_fotografico(tela, foto, escurecer=0.80, desfoque=0.030)

    m, pad = W * 0.045, W * 0.055

    # com o logo centralizado no topo, tudo desce: título abaixo dele, e a foto
    # abaixo do título. Nada mais se sobrepõe.
    topo_tit = m
    if mostrar_logo and logo_pos in ("tl", "tr", "tc"):
        topo_tit = m + _altura_logo(logo or LOGO_PADRAO, W, logo_pct) + W * 0.030
    # espaço reservado no rodapé para o @ centralizado
    rodape = W * 0.090 if mostrar_arroba else m
    fundo_livre = (H - round(H * 0.13) - rodape - W * 0.035) if lower else H - rodape

    area = None
    if titulo:
        area = (_titulo(tela, titulo, topo_tit, desenhar=False) + W * 0.028, fundo_livre)
    else:
        area = (topo_tit, fundo_livre)

    if foto:
        _foto(tela, foto, modo, area, cortar_rodape, cortar_topo)
    _veu_inferior(tela)
    if titulo:
        _titulo(tela, titulo, topo_tit)
    if lower:
        _lower(tela, lower[0], lower[1], margem_baixo=rodape)
    if mostrar_logo:
        _logo(tela, logo or LOGO_PADRAO, logo_pct, logo_pos)
    if mostrar_arroba:
        _arroba(tela, arroba)

    return _salvar(tela.img, saida, alvo, master)


def gerar_card(saida, versiculo, referencia, chamada=None, formato="4x5",
               logo=None, arroba=None, aspas=True, fundo=None,
               escala=ESCALA_PADRAO, master=None):
    """Card de versículo. Com `fundo` (céu, cachoeira, águia…) a foto entra
    atrás com névoa e vinheta; sem ele, fica o degradê da marca."""
    alvo = FORMATOS[formato]
    W, H = alvo[0] * escala, alvo[1] * escala

    tela = Tela(_degrade_diagonal(W, H, FUNDO).convert("RGB"))
    if fundo:
        _fundo_fotografico(tela, fundo)

    caminho_logo = logo or LOGO_PADRAO
    _logo(tela, caminho_logo, 17, "tc")
    abaixo = W * 0.045 + _altura_logo(caminho_logo, W, 17)

    tela.texto_espacado((W / 2, abaixo + W * 0.078), "SAGRADO ARCO REAL",
                        cinzel(W * 0.038), OURO, W * 0.007)
    regua = abaixo + W * 0.106
    tela.d.rectangle((W / 2 - W * 0.07, regua,
                      W / 2 + W * 0.07, regua + W * 0.0035), fill=OURO)

    corpo = f'“{versiculo}”' if aspas else versiculo
    tam = W * 0.080
    while tam > W * 0.038:
        if len(_quebrar(tela, corpo, cormorant(tam, "SemiBold"), W * 0.82)) <= 6:
            break
        tam *= 0.94
    fonte = cormorant(tam, "SemiBold")
    linhas = _quebrar(tela, corpo, fonte, W * 0.82)

    y = H * 0.54 - (len(linhas) * tam * 1.28) / 2
    for linha in linhas:
        tela.texto((W / 2, y), linha, fonte, (250, 248, 253), anchor="ma",
                   sombra=0.009, forca=225)
        y += tam * 1.28

    tela.texto_espacado((W / 2, y + H * 0.050), referencia.upper(),
                        montserrat(W * 0.036, "Bold"), OURO, W * 0.006)

    if chamada:
        f = montserrat(W * 0.030, "Medium")
        linhas_c = _quebrar(tela, chamada, f, W * 0.78)
        yc = H * 0.855 - (len(linhas_c) - 1) * W * 0.021
        for linha in linhas_c:
            tela.texto((W / 2, yc), linha, f, (220, 216, 234), anchor="ma",
                       sombra=0.005)
            yc += W * 0.042

    _arroba(tela, arroba)
    return _salvar(tela.img, saida, alvo, master)
