"""
rastrear.py — Em qual rosto o close 9:16 fica, segundo a segundo.

Num podcast de duas pessoas, recortar um retângulo fixo deixa metade do
episódio com o ouvinte na tela e quem fala fora dela. A Opus e a Klap
resolvem com "detecção de orador ativo"; aqui é a mesma ideia, leve:
rostos pelo YuNet (modelo de 230 KB que viaja com o motor) e a BOCA que
mais se mexe diz quem está falando.

    segmentos(midia, de, ate)  →  [(t_relativo, foco), ...]

`foco` é a fração horizontal do recorte (0 = borda esquerda, 1 = direita),
pronta para `cortes.cortar(..., modo="recorte")`. Os cortes são secos, como
as ferramentas fazem: ninguém quer a câmera deslizando entre dois rostos.

Como decide, em ordem:
  1. amostra o trecho a 4 quadros/s em 640 px, cinza, via ffmpeg
  2. separa os PLANOS: podcast editado troca de câmera, e cada plano tem
     suas pessoas em seus lugares
  3. em cada plano, detecta rostos e agrupa por posição horizontal em
     "faixas" (uma por pessoa); a boca de cada faixa vem dos pontos do YuNet
  4. movimento = diferença entre amostras na região FIXA da boca de cada
     faixa, menos a diferença na testa/olhos (cabeça mexendo não conta).
     Região fixa porque o detector falha justo com a boca aberta, e a pessoa
     não sai do lugar dentro do plano
  5. por janela de 1 s, a faixa com mais movimento fala; só troca se a outra
     passa de 1,3x, e nenhum segmento dura menos de 1,5 s
  6. plano com um rosto só: centra nele. Sem rosto: centro do quadro

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
RAIO_FAIXA = 0.12       # fração da largura: rostos mais perto que isto são o mesmo
PRESENCA_MINIMA = 0.15  # faixa vista em menos de 15% das amostras é ruído
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


def _faixas(deteccoes, largura):
    """Agrupa rostos por centro horizontal.

    Devolve [{cx, caixa, boca, presenca}], com caixa e boca MEDIANAS do plano:
    é nessa região fixa que o movimento é medido, detecte ou não cada quadro.
    """
    todas = sorted((r for ds in deteccoes for r in ds), key=lambda r: r[0] + r[2] / 2)
    grupos, atual = [], []
    for r in todas:
        c = (r[0] + r[2] / 2) / largura
        if atual and c - (atual[-1][0] + atual[-1][2] / 2) / largura > RAIO_FAIXA:
            grupos.append(atual)
            atual = []
        atual.append(r)
    if atual:
        grupos.append(atual)
    n = max(1, len(deteccoes))
    faixas = []
    for g in grupos:
        presenca = len(g) / n
        if presenca < PRESENCA_MINIMA:
            continue
        med = np.median(np.array(g), axis=0)
        faixas.append({"cx": float((med[0] + med[2] / 2) / largura),
                       "caixa": med[:4], "boca": med[4:6], "presenca": presenca})
    return faixas


def movimento_boca(quadros, faixas):
    """(N, F): quanto a boca de cada faixa mexeu entre a amostra e a anterior."""
    H, W = quadros.shape[1:]
    regioes = []
    for f in faixas:
        x, y, w, h = f["caixa"]
        bx, by = f["boca"]
        rw, rh = w * 0.5, h * 0.3
        boca = (slice(int(max(0, by - rh / 2)), int(min(H, by + rh / 2))),
                slice(int(max(0, bx - rw / 2)), int(min(W, bx + rw / 2))))
        cima = (slice(int(max(0, y)), int(min(H, y + h * 0.45))),
                slice(int(max(0, x)), int(min(W, x + w))))
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
    """[(t_relativo_ao_plano, faixa)] — quem fala, com histerese e sem picotar."""
    por_janela = max(1, int(round(JANELA / PASSO)))
    atual = int(np.argmax(mov.sum(axis=0)))      # quem mais falou abre o plano
    escolhas = []
    for ini in range(0, len(mov), por_janela):
        m = mov[ini: ini + por_janela].sum(axis=0)
        melhor = int(np.argmax(m))
        if melhor != atual and m[melhor] > TROCA * m[atual] and m[melhor] > 0:
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


def _foco(cx, largura, altura):
    """Centro do rosto (fração) → fração do recorte 9:16, com as bordas presas."""
    corte = altura * 9 / 16
    folga = largura - corte
    if folga <= 0:
        return 0.5
    return float(min(1.0, max(0.0, (cx * largura - corte / 2) / folga)))


def segmentos(midia, de, ate, verboso=True):
    """[(t_relativo_inicio, foco)] — quem está na tela em cada momento."""
    quadros = amostrar(midia, de, ate)
    if len(quadros) == 0:
        return [(0.0, 0.5)]
    altura, largura = quadros.shape[1:]
    detectar = Detector()
    saida = []
    for (a, b) in cenas(quadros):
        t0 = a * PASSO
        ds = [detectar(q) for q in quadros[a:b]]
        faixas = _faixas(ds, largura)
        if not faixas:
            segs = [(t0, 0.5)]
        elif len(faixas) == 1:
            segs = [(t0, _foco(faixas[0]["cx"], largura, altura))]
        else:
            mov = movimento_boca(quadros[a:b], faixas)
            segs = [(t0 + t, _foco(faixas[i]["cx"], largura, altura))
                    for t, i in _decidir(mov, (b - a) * PASSO)]
        if verboso:
            print(f"→ plano {t0:6.2f}s–{b * PASSO:6.2f}s ({detectar.nome}): "
                  f"{len(faixas)} pessoa(s) "
                  + ", ".join(f"x={f['cx']:.2f} ({f['presenca']:.0%})" for f in faixas),
                  file=sys.stderr)
            for t, f in segs:
                print(f"    {t:6.2f}s → foco {f:.2f}", file=sys.stderr)
        saida.extend(segs)

    fundido = []
    for t, f in saida:
        if fundido and abs(fundido[-1][1] - f) < 0.01:
            continue
        fundido.append((t, f))
    return fundido


def expressao_x(segs, largura_px, altura_px):
    """Expressão do ffmpeg para o `x` do crop: pedaços constantes no tempo."""
    corte = int(altura_px * 9 / 16)
    folga = largura_px - corte
    xs = [int(round(f * folga)) for _, f in segs]
    expr = str(xs[-1])
    for (t, _), x in zip(reversed(segs[1:]), reversed(xs[:-1])):
        expr = f"if(lt(t,{t:.3f}),{x},{expr})"
    return expr
