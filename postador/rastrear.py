"""
rastrear.py — Em qual rosto o close 9:16 fica, segundo a segundo.

Num podcast de duas ou três pessoas, recortar um retângulo fixo deixa quem
ouve na tela e quem fala fora dela. A Opus e a Klap resolvem com "detecção
de orador ativo"; aqui é a mesma ideia, leve: rostos pelo YuNet (modelo de
230 KB que viaja com o motor) e a BOCA que mais se mexe diz quem fala.

    segmentos(midia, de, ate)  →  [(t_relativo, centro_x), ...]

`centro_x` é a fração horizontal (0 = borda esquerda, 1 = direita) onde o
rosto escolhido está; `expressao_x` converte isso no `x` do crop do ffmpeg.
Os cortes são secos, como as ferramentas fazem: ninguém quer a câmera
deslizando entre dois rostos.

Como decide, em ordem:
  1. amostra o trecho a 4 quadros/s em 640 px, cinza, via ffmpeg
  2. separa os PLANOS: podcast editado troca de câmera, e cada plano tem
     suas pessoas em seus lugares
  3. em cada plano, detecta rostos e agrupa por posição E tamanho (o quadro
     da parede atrás tem rosto também, e o YuNet acha; ele fica na mesma
     coluna que a pessoa, mas noutra altura e noutro tamanho)
  4. descarta grupo PARADO: retrato pintado não pisca nem respira
  5. um rosto muito maior que os outros é close de uma pessoa só: centra nele
  6. com dois ou mais, movimento = diferença entre amostras na região FIXA
     da boca de cada um, menos a diferença na testa/olhos (cabeça mexendo
     não conta). Região fixa porque o detector falha justo com a boca aberta
     e a pessoa não sai do lugar dentro do plano
  7. por janela de 1 s, quem mais mexe a boca fala; só troca se o outro
     passa de 1,3x, e nenhum segmento dura menos de 1,5 s

Sem o modelo YuNet cai no Haar cascade do OpenCV, que é pior de ângulo e de
boca aberta, mas não depende de arquivo nenhum.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

MOTOR = Path(__file__).resolve().parent
YUNET = MOTOR / "assets" / "modelos" / "face_detection_yunet_2023mar.onnx"

PASSO = 0.25            # s entre amostras (4 quadros/s)
LARGURA_AMOSTRA = 640
JANELA = 1.0            # s por decisão
MIN_SEGMENTO = 1.5      # s
TROCA = 1.3             # a outra pessoa precisa mexer 30% mais a boca
FALA = 2.5              # movimento de boca por janela abaixo disto é ruído
RAIO_GRUPO = 0.08       # fração da largura: rostos mais perto que isto, e de
                        # tamanho parecido, são a mesma pessoa
PRESENCA_MINIMA = 0.15  # grupo visto em menos de 15% das amostras é ruído
PARADO = 1.0            # diferença média (0–255) dentro do rosto abaixo disto
                        # é retrato na parede, não gente
CLOSE = 2.5             # rosto com área 2,5x maior que o segundo é close
CORTE_DE_CENA = 28.0    # diferença média (0–255) entre amostras que marca troca de plano


def _dimensoes(midia):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(midia)],
        capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def amostrar(midia, de, ate):
    """Quadros cinza (N, h, 640) a 4/s, decodificados pelo ffmpeg."""
    w, h = _dimensoes(midia)
    hs = int(round(h * LARGURA_AMOSTRA / w / 2)) * 2
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{de:.3f}", "-t", f"{ate - de:.3f}",
           "-i", str(midia), "-vf", f"fps={1/PASSO:g},scale={LARGURA_AMOSTRA}:{hs}",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (LARGURA_AMOSTRA * hs)
    return np.frombuffer(raw, np.uint8)[: n * LARGURA_AMOSTRA * hs].reshape(n, hs, LARGURA_AMOSTRA)


class Detector:
    """Rostos num quadro cinza: [(x, y, w, h, boca_x, boca_y)], em pixels."""

    def __init__(self):
        import cv2
        self.cv2 = cv2
        self.yunet = None
        if YUNET.exists() and YUNET.stat().st_size > 10_000:
            self.yunet = cv2.FaceDetectorYN.create(
                str(YUNET), "", (LARGURA_AMOSTRA, LARGURA_AMOSTRA), 0.6, 0.3, 50)
        else:
            self.haar = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    @property
    def nome(self):
        return "YuNet" if self.yunet is not None else "Haar"

    def __call__(self, q):
        h, w = q.shape
        if self.yunet is not None:
            self.yunet.setInputSize((w, h))
            _, rostos = self.yunet.detect(self.cv2.cvtColor(q, self.cv2.COLOR_GRAY2BGR))
            if rostos is None:
                return []
            # colunas: x y w h, olho_d olho_e nariz boca_d boca_e (x,y cada), score
            return [(float(r[0]), float(r[1]), float(r[2]), float(r[3]),
                     float((r[10] + r[12]) / 2), float((r[11] + r[13]) / 2))
                    for r in rostos]
        minimo = max(24, h // 12)
        return [(float(x), float(y), float(bw), float(bh), x + bw / 2, y + bh * 0.8)
                for (x, y, bw, bh) in self.haar.detectMultiScale(
                    q, scaleFactor=1.1, minNeighbors=4, minSize=(minimo, minimo))]


def cenas(quadros):
    """Índices [a, b) de cada plano: corte quando a imagem muda de uma vez."""
    limites = [0]
    for t in range(1, len(quadros)):
        d = np.abs(quadros[t].astype(np.int16) - quadros[t - 1].astype(np.int16)).mean()
        if d > CORTE_DE_CENA:
            limites.append(t)
    limites.append(len(quadros))
    return [(limites[i], limites[i + 1]) for i in range(len(limites) - 1)
            if limites[i + 1] > limites[i]]


def _recorte(caixa, H, W, y0=0.0, y1=1.0, x0=0.0, x1=1.0):
    x, y, w, h = caixa
    return (slice(int(max(0, y + h * y0)), int(min(H, y + h * y1))),
            slice(int(max(0, x + w * x0)), int(min(W, x + w * x1))))


def _movimento_na_caixa(quadros, caixa):
    """Diferença média entre amostras consecutivas dentro da caixa."""
    H, W = quadros.shape[1:]
    reg = _recorte(caixa, H, W)
    if quadros[0][reg].size == 0 or len(quadros) < 2:
        return 0.0
    a = quadros[:-1, reg[0], reg[1]].astype(np.int16)
    b = quadros[1:, reg[0], reg[1]].astype(np.int16)
    return float(np.abs(a - b).mean())


def pessoas(deteccoes, quadros):
    """Quem está no plano, de verdade.

    Devolve [{cx, caixa, boca, presenca, movimento, area}] com caixa e boca
    MEDIANAS do plano: é nessa região fixa que o movimento é medido,
    detecte ou não cada quadro. Retratos na parede saem no filtro de
    movimento; grupos fugazes, no de presença.
    """
    H, W = quadros.shape[1:]
    grupos = []                        # cada um: {"itens": [(quadro, rosto)]}
    for t, ds in enumerate(deteccoes):
        for r in ds:
            cx, cy, tam = (r[0] + r[2] / 2) / W, (r[1] + r[3] / 2) / W, r[2]
            for g in grupos:
                gx, gy, gt = g["ref"]
                if abs(cx - gx) < RAIO_GRUPO and abs(cy - gy) < RAIO_GRUPO \
                        and 0.6 < tam / gt < 1.6:
                    g["itens"].append((t, r))
                    break
            else:
                grupos.append({"ref": (cx, cy, tam), "itens": [(t, r)]})

    n = max(1, len(deteccoes))
    saida = []
    for g in grupos:
        presenca = len({t for t, _ in g["itens"]}) / n
        if presenca < PRESENCA_MINIMA:
            continue
        med = np.median(np.array([r for _, r in g["itens"]]), axis=0)
        caixa = med[:4]
        mov = _movimento_na_caixa(quadros, caixa)
        saida.append({"cx": float((caixa[0] + caixa[2] / 2) / W), "caixa": caixa,
                      "boca": med[4:6], "presenca": presenca, "movimento": mov,
                      "area": float(caixa[2] * caixa[3])})
    vivos = [p for p in saida if p["movimento"] >= PARADO]
    return vivos if vivos else saida


def movimento_boca(quadros, faixas):
    """(N, F): quanto a boca de cada pessoa mexeu entre a amostra e a anterior."""
    H, W = quadros.shape[1:]
    regioes = []
    for f in faixas:
        x, y, w, h = f["caixa"]
        bx, by = f["boca"]
        boca = _recorte((bx - w * 0.25, by - h * 0.15, w * 0.5, h * 0.3), H, W)
        cima = _recorte((x, y, w, h * 0.45), H, W)
        regioes.append((boca, cima))
    mov = np.zeros((len(quadros), len(faixas)))
    for t in range(1, len(quadros)):
        a, b = quadros[t - 1].astype(np.int16), quadros[t].astype(np.int16)
        for i, (boca, cima) in enumerate(regioes):
            d_boca = np.abs(a[boca] - b[boca]).mean() if a[boca].size else 0.0
            d_cima = np.abs(a[cima] - b[cima]).mean() if a[cima].size else 0.0
            mov[t, i] = max(0.0, d_boca - d_cima)
    return mov


def _decidir(mov, duracao):
    """[(t_relativo_ao_plano, pessoa)] — quem fala, com histerese e sem picotar."""
    por_janela = max(1, int(round(JANELA / PASSO)))
    atual = int(np.argmax(mov.sum(axis=0)))      # quem mais falou abre o plano
    escolhas = []
    for ini in range(0, len(mov), por_janela):
        m = mov[ini: ini + por_janela].sum(axis=0)
        melhor = int(np.argmax(m))
        # Troca só com fala de verdade: quem fala marca 20 a 45 por janela,
        # ruído de quem ouve marca 0 a 1,5. Sem o piso, a primeira janela
        # trocava para qualquer um acima de zero.
        if melhor != atual and m[melhor] > TROCA * m[atual] and m[melhor] > FALA:
            atual = melhor
        escolhas.append([ini * PASSO, atual])
    segs = []
    for t, i in escolhas:
        if segs and segs[-1][1] == i:
            continue
        segs.append([t, i])
    k = 1
    while k < len(segs):
        fim = segs[k + 1][0] if k + 1 < len(segs) else duracao
        if fim - segs[k][0] < MIN_SEGMENTO:
            del segs[k]
            if k < len(segs) and segs[k][1] == segs[k - 1][1]:
                del segs[k]
            continue
        k += 1
    return [(t, i) for t, i in segs]


def segmentos(midia, de, ate, verboso=True):
    """[(t_relativo_inicio, centro_x)] — quem está na tela em cada momento."""
    quadros = amostrar(midia, de, ate)
    if len(quadros) == 0:
        return [(0.0, 0.5)]
    detectar = Detector()
    saida = []
    for (a, b) in cenas(quadros):
        t0 = a * PASSO
        bloco = quadros[a:b]
        gente = pessoas([detectar(q) for q in bloco], bloco)
        gente.sort(key=lambda p: -p["area"])
        if not gente:
            segs = [(t0, 0.5)]
        elif len(gente) == 1 or gente[0]["area"] >= CLOSE * gente[1]["area"]:
            segs = [(t0, gente[0]["cx"])]
        else:
            mov = movimento_boca(bloco, gente)
            segs = [(t0 + t, gente[i]["cx"]) for t, i in _decidir(mov, (b - a) * PASSO)]
        if verboso:
            print(f"→ plano {t0:6.2f}s–{b * PASSO:6.2f}s ({detectar.nome}): "
                  f"{len(gente)} pessoa(s) "
                  + ", ".join(f"x={p['cx']:.2f} (vista {p['presenca']:.0%}, "
                              f"mexe {p['movimento']:.1f})" for p in gente),
                  file=sys.stderr)
            for t, cx in segs:
                print(f"    {t:6.2f}s → centro {cx:.2f}", file=sys.stderr)
        saida.extend(segs)

    fundido = []
    for t, cx in saida:
        if fundido and abs(fundido[-1][1] - cx) < 0.01:
            continue
        fundido.append((t, cx))
    return fundido


def expressao_x(segs, largura_px, corte_px):
    """Expressão do ffmpeg para o `x` do crop: pedaços constantes no tempo.

    `corte_px` é a largura do recorte; o rosto fica no centro dele, com as
    bordas do quadro presas.
    """
    folga = max(0, largura_px - corte_px)
    xs = [int(round(min(folga, max(0.0, cx * largura_px - corte_px / 2)))) for _, cx in segs]
    expr = str(xs[-1])
    for (t, _), x in zip(reversed(segs[1:]), reversed(xs[:-1])):
        expr = f"if(lt(t,{t:.3f}),{x},{expr})"
    return expr
