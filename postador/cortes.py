"""
cortes.py — Recorta trechos de um vídeo longo (podcast) em reels 9:16 com
legenda queimada palavra a palavra.

Por que isto e não a Klap: a Klap cobra por operação na API (entrada do vídeo,
cada corte, cada exportação) e não tem MCP. O que ela faz por baixo é o que
está aqui — transcrever, escolher o trecho, reenquadrar, legendar — e as duas
primeiras etapas o Claude faz lendo a transcrição. Fica a Klap grátis, se
quiser, só como segunda opinião sobre QUAL trecho cortar.

As três etapas, separadas de propósito, porque a primeira é lenta e as outras
são instantâneas e vão ser refeitas várias vezes até o corte agradar:

    python -m postador.cortes transcrever PODCAST.mp4
        → PODCAST.palavras.json   (tempo de cada palavra; demora, roda 1 vez)

    python -m postador.cortes ler PODCAST.palavras.json
        → a transcrição com relógio, para escolher os trechos

    python -m postador.cortes cortar PODCAST.mp4 --de 12:03 --ate 13:01 \\
        --palavras PODCAST.palavras.json --saida cortes/corte1.mp4 \\
        [--modo moldura|recorte] [--foco 0.5] [--titulo "O gancho do corte"]

Dois enquadramentos:

    moldura   o vídeo 16:9 inteiro no meio, fundo desfocado, legenda embaixo.
              Ninguém sai do quadro. É o padrão para podcast com duas pessoas.
    recorte   corta um retângulo 9:16 do quadro original (close). `--foco auto`
              (padrão) segue quem está falando, via rastrear.py; um número
              fixa: 0.0 borda esquerda, 0.5 centro, 1.0 borda direita.

A legenda é ASS renderizada pelo libass dentro do ffmpeg, com a Montserrat do
motor: frase curta (até 4 palavras), caixa alta, palavra falada em amarelo.
O `.ass` fica ao lado do `.mp4` para ajuste fino à mão, se precisar.

Zona segura: a legenda fica acima dos ~400 px que a interface do Instagram
cobre embaixo e o título abaixo dos ~250 px cobertos em cima.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
FONTES = MOTOR / "assets" / "fontes"

LARGURA, ALTURA = 1080, 1920

# Estilo da legenda. Cores em ASS são &HAABBGGRR (alfa, azul, verde, vermelho).
COR_TEXTO = "&H00FFFFFF"      # branco
COR_ATIVA = "&H0000D4FF"      # amarelo #FFD400 — a palavra sendo dita
COR_BORDA = "&H00000000"      # preto
COR_SOMBRA = "&H80000000"     # preto meio transparente
TAM_LEGENDA = 74
TAM_TITULO = 60
MARGEM_LEGENDA = 470           # px a partir de baixo: acima da UI do Instagram
MARGEM_TITULO = 260            # px a partir de cima: abaixo da UI do Instagram

MAX_PALAVRAS_BLOCO = 4
MAX_CARACTERES_BLOCO = 24
MAX_DURACAO_BLOCO = 1.8        # s
PAUSA_QUEBRA = 0.6             # s de silêncio que fecha o bloco


# ---------------------------------------------------------------------------
# Tempo
# ---------------------------------------------------------------------------

def segundos(txt) -> float:
    """'1:02:03.5', '12:03', '723.5' → segundos."""
    if isinstance(txt, (int, float)):
        return float(txt)
    partes = [float(p) for p in str(txt).strip().split(":")]
    total = 0.0
    for p in partes:
        total = total * 60 + p
    return total


def relogio(seg: float) -> str:
    seg = max(0.0, seg)
    h, r = divmod(int(seg), 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _tempo_ass(seg: float) -> str:
    seg = max(0.0, seg)
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


# ---------------------------------------------------------------------------
# 1. Transcrever
# ---------------------------------------------------------------------------

def extrair_audio(midia: Path, saida: Path) -> Path:
    """WAV mono 16 kHz — o que o Whisper quer, e 200x menor que o vídeo.

    Ler o áudio direto do .mp4 de 10 GB funciona, mas qualquer segunda passada
    (outro modelo, outro trecho) teria que percorrer o arquivo inteiro de novo.
    """
    saida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
         "-i", str(midia), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(saida)],
        check=True,
    )
    return saida


def _ler_wav(caminho, de=None, ate=None):
    """WAV mono 16 kHz → (float32 em [-1, 1], deslocamento em s)."""
    import wave

    import numpy as np

    with wave.open(str(caminho), "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (16000, 1, 2):
            raise SystemExit(f"{caminho}: esperava WAV mono 16 kHz 16 bit")
        n = w.getnframes()
        a = min(n, max(0, int(segundos(de) * 16000))) if de is not None else 0
        b = min(n, int(segundos(ate) * 16000)) if ate is not None else n
        w.setpos(a)
        bruto = w.readframes(max(0, b - a))
    return np.frombuffer(bruto, np.int16).astype(np.float32) / 32768.0, a / 16000


def transcrever(midia, modelo="small", idioma="pt", saida=None,
                de=None, ate=None) -> Path:
    """Transcreve com tempo por palavra e grava `<midia>.palavras.json`.

    `small` lê um podcast de 1 h em ~10 min de CPU e basta para ESCOLHER os
    trechos. Para a legenda final, rode de novo só o trecho escolhido
    (`--de/--ate`) com `medium` ou `large-v3`: palavra certa no tempo certo.
    """
    from faster_whisper import WhisperModel   # pesado; só quem transcreve paga

    midia = Path(midia)
    saida = Path(saida) if saida else midia.with_suffix(".palavras.json")
    wav = midia.with_suffix(".16k.wav")
    if not wav.exists():
        print(f"→ extraindo áudio para {wav.name}", file=sys.stderr)
        extrair_audio(midia, wav)

    # O vetor vai direto ao modelo, sem o PyAV que o faster-whisper usaria
    # para abrir o arquivo: a versão do PyAV muda a assinatura e quebra.
    # Com `--de/--ate` recorta o vetor: 1 min de áudio com modelo grande sai
    # em segundos, não em horas.
    audio, desloc = _ler_wav(wav, de, ate)

    print(f"→ carregando Whisper {modelo} (CPU int8)", file=sys.stderr)
    w = WhisperModel(modelo, device="cpu", compute_type="int8")
    segmentos, info = w.transcribe(
        audio, language=idioma, beam_size=5,
        word_timestamps=True, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
    )
    print(f"→ {info.duration/60:.1f} min de áudio, idioma {info.language} "
          f"({info.language_probability:.0%})", file=sys.stderr)

    lista = []
    for s in segmentos:
        palavras = [
            {"p": p.word.strip(), "i": round(p.start + desloc, 3),
             "f": round(p.end + desloc, 3)}
            for p in (s.words or []) if p.word.strip()
        ]
        lista.append({
            "inicio": round(s.start + desloc, 3),
            "fim": round(s.end + desloc, 3),
            "texto": s.text.strip(),
            "palavras": palavras,
        })
        print(f"  {relogio(s.end + desloc)}  {s.text.strip()[:70]}",
              file=sys.stderr)

    saida.write_text(json.dumps(
        {"midia": midia.name, "modelo": modelo, "idioma": idioma,
         "segmentos": lista}, ensure_ascii=False, indent=1))
    print(f"✓ {saida}  ({len(lista)} segmentos)", file=sys.stderr)
    return saida


def carregar_palavras(caminho) -> list[dict]:
    dados = json.loads(Path(caminho).read_text())
    return [p for s in dados["segmentos"] for p in s["palavras"]]


# ---------------------------------------------------------------------------
# 2. Ler — para escolher o trecho
# ---------------------------------------------------------------------------

def ler(caminho, janela=45) -> str:
    """A transcrição em blocos de `janela` segundos, com relógio na frente.

    É isto que o Claude lê para apontar os trechos. Blocos curtos porque o
    corte bom tem 40–75 s: gancho, desenvolvimento, fecho.
    """
    dados = json.loads(Path(caminho).read_text())
    linhas, bloco, ini = [], [], None
    for s in dados["segmentos"]:
        if ini is None:
            ini = s["inicio"]
        bloco.append(s["texto"])
        if s["fim"] - ini >= janela:
            linhas.append(f"[{relogio(ini)} → {relogio(s['fim'])}] "
                          + " ".join(bloco))
            bloco, ini = [], None
    if bloco:
        linhas.append(f"[{relogio(ini)} → {relogio(dados['segmentos'][-1]['fim'])}] "
                      + " ".join(bloco))
    texto = "\n\n".join(linhas)
    print(texto)
    return texto


# ---------------------------------------------------------------------------
# 3. Legenda
# ---------------------------------------------------------------------------

def _blocos(palavras: list[dict]) -> list[list[dict]]:
    """Agrupa palavras em frases curtas: até 4 palavras, ~1,8 s, 24 letras.

    Fecha também em pontuação e em pausa — a legenda tem que respirar junto
    com quem fala, senão vira teleprompter.
    """
    blocos, atual = [], []

    def fecha():
        if atual:
            blocos.append(list(atual))
            atual.clear()

    for n, p in enumerate(palavras):
        if atual:
            dur = p["f"] - atual[0]["i"]
            chars = sum(len(x["p"]) for x in atual) + len(atual) + len(p["p"])
            pausa = p["i"] - atual[-1]["f"]
            if (len(atual) >= MAX_PALAVRAS_BLOCO or dur > MAX_DURACAO_BLOCO
                    or chars > MAX_CARACTERES_BLOCO or pausa > PAUSA_QUEBRA):
                fecha()
        atual.append(p)
        if p["p"][-1:] in ".!?;:":
            fecha()
    fecha()
    return blocos


def _esc_ass(txt: str) -> str:
    return txt.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def gerar_ass(palavras, de, ate, titulo=None, maiusculas=True) -> str:
    """Um evento por palavra: a frase inteira na tela, a palavra ativa em
    amarelo. Mais robusto que o karaokê `\\k`, que alguns players ignoram."""
    de, ate = segundos(de), segundos(ate)
    # Só palavra que COMEÇA dentro do corte: a que começou antes já está
    # pela metade no áudio e apareceria inteira na tela.
    dentro = [p for p in palavras if p["i"] >= de - 0.05 and p["i"] < ate]

    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {LARGURA}
PlayResY: {ALTURA}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Legenda,Montserrat,{TAM_LEGENDA},{COR_TEXTO},{COR_ATIVA},{COR_BORDA},{COR_SOMBRA},-1,0,0,0,100,100,1,0,1,6,3,2,60,60,{MARGEM_LEGENDA},1
Style: Titulo,Montserrat,{TAM_TITULO},{COR_TEXTO},{COR_ATIVA},{COR_BORDA},&H99000000,-1,0,0,0,100,100,0,0,3,14,0,8,90,90,{MARGEM_TITULO},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    eventos = []
    fim_clipe = ate - de
    if titulo:
        t = _esc_ass(titulo.upper() if maiusculas else titulo)
        eventos.append(f"Dialogue: 0,{_tempo_ass(0)},{_tempo_ass(fim_clipe)},"
                       f"Titulo,,0,0,0,,{t}")

    blocos = _blocos(dentro)
    for n, bloco in enumerate(blocos):
        # O bloco some 0,15 s depois da última palavra OU quando o próximo
        # entra: dois blocos na tela ao mesmo tempo viram quatro linhas.
        fim_bloco = bloco[-1]["f"] + 0.15
        if n + 1 < len(blocos):
            fim_bloco = min(fim_bloco, blocos[n + 1][0]["i"])
        for k, p in enumerate(bloco):
            ini = max(0.0, p["i"] - de)
            fim = (bloco[k + 1]["i"] if k + 1 < len(bloco) else fim_bloco) - de
            fim = min(fim, fim_clipe)
            if fim <= ini:
                continue
            partes = []
            for j, q in enumerate(bloco):
                w = _esc_ass(q["p"].upper() if maiusculas else q["p"])
                if j == k:
                    partes.append(f"{{\\c{COR_ATIVA}\\fscx106\\fscy106}}{w}{{\\r}}")
                else:
                    partes.append(w)
            eventos.append(f"Dialogue: 1,{_tempo_ass(ini)},{_tempo_ass(fim)},"
                           f"Legenda,,0,0,0,,{' '.join(partes)}")
    return cab + "\n".join(eventos) + "\n"


# ---------------------------------------------------------------------------
# 4. Cortar
# ---------------------------------------------------------------------------

ALTURA_COM_TARJA = 0.82    # fração do quadro que sobra acima da tarja de TV


def _tem_tarja(midia, de, ate) -> bool:
    """Há letreiro azul de TV na faixa de baixo em algum momento do trecho?

    Mede, 1 vez por segundo, a fração de azul SATURADO nos 18% de baixo do
    quadro. Paletó azul-marinho é azul escuro e dessaturado: no estúdio da
    GLESP ele chega a 0,19; a tarja fica em 0,30 ou mais. Basta aparecer em
    3 s do trecho: o enquadramento é um só para o corte inteiro, e tarja
    cortada ao meio por 3 s já é feio.
    """
    import cv2
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{de:.3f}", "-t", f"{ate - de:.3f}",
         "-i", str(midia), "-vf", "fps=1,scale=320:-2", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if not raw:
        return False
    # altura da amostra: 320 de largura, proporção do vídeo
    largura, altura = _dimensoes_video(midia)
    h = int(round(altura * 320 / largura / 2)) * 2
    n = len(raw) // (h * 320 * 3)
    if n == 0:
        return False
    seq = np.frombuffer(raw, np.uint8)[: n * h * 320 * 3].reshape(n, h, 320, 3)
    com_tarja = 0
    for img in seq:
        hsv = cv2.cvtColor(np.ascontiguousarray(img[int(h * 0.82):]), cv2.COLOR_RGB2HSV)
        azul = ((hsv[..., 0] > 100) & (hsv[..., 0] < 130)
                & (hsv[..., 1] > 110) & (hsv[..., 2] > 60)).mean()
        com_tarja += azul > 0.25
    return com_tarja >= 3


def _dimensoes_video(midia):
    from .rastrear import _dimensoes
    return _dimensoes(midia)


def cortar(midia, de, ate, saida, palavras=None, modo="moldura", foco="auto",
           titulo=None, qualidade=18, barra="auto") -> Path:
    """Recorta [de, ate] de `midia` num reel 1080x1920 com legenda queimada.

    `palavras`: caminho do .palavras.json, lista de palavras, ou None (sem
    legenda). `foco` só vale no modo `recorte`: "auto" ou fração 0–1.
    `barra`: "auto" detecta tarja de TV embaixo e a corta fora; True/False força.
    """
    midia, saida = Path(midia), Path(saida)
    de_s, ate_s = segundos(de), segundos(ate)
    if ate_s <= de_s:
        raise SystemExit(f"--ate ({ate}) tem que vir depois de --de ({de})")
    saida.parent.mkdir(parents=True, exist_ok=True)

    if modo == "moldura":
        video = (
            "[0:v]split=2[fundo][frente];"
            f"[fundo]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
            f"crop={LARGURA}:{ALTURA},gblur=sigma=45,eq=brightness=-0.18:saturation=0.75[fd];"
            f"[frente]scale={LARGURA}:-2[fr];"
            "[fd][fr]overlay=(W-w)/2:(H-h)/2-110,format=yuv420p[v0]"
        )
    elif modo == "recorte":
        from .rastrear import _dimensoes, expressao_x, segmentos
        w, h = _dimensoes(midia)
        # Tarja de TV embaixo (nome do programa, letreiro rolando) vira um
        # pedaço ilegível no 9:16. Se está lá, o recorte fica com os 82% de
        # cima do quadro, presos ao topo: o rosto nunca está na tarja.
        alt = ALTURA_COM_TARJA if (
            barra is True or (barra == "auto" and _tem_tarja(midia, de_s, ate_s))) else 1.0
        corte_h = int(h * alt) // 2 * 2
        corte_w = int(corte_h * 9 / 16) // 2 * 2
        if str(foco).strip().lower() == "auto":
            # Segue quem fala: rostos + boca que mexe, cortes secos entre eles.
            x = expressao_x(segmentos(midia, de_s, ate_s), w, corte_w)
        else:
            x = str(int((w - corte_w) * min(1.0, max(0.0, float(foco)))))
        video = (
            f"[0:v]crop={corte_w}:{corte_h}:'{x}':0,"
            f"scale={LARGURA}:{ALTURA},format=yuv420p[v0]"
        )
    else:
        raise SystemExit(f"modo desconhecido: {modo} (moldura|recorte)")

    # O .ass vai com nome simples e o ffmpeg roda de dentro da pasta de saída:
    # o filtro `subtitles` engasga com dois-pontos, vírgula e aspas no caminho.
    ass_tmp = saida.parent / f"_legenda_{os.getpid()}.ass"
    ass_final = saida.with_suffix(".ass")
    tem_legenda = palavras is not None or titulo
    if tem_legenda:
        lista = ([] if palavras is None else
                 carregar_palavras(palavras) if isinstance(palavras, (str, Path))
                 else palavras)
        ass_tmp.write_text(gerar_ass(lista, de_s, ate_s, titulo=titulo))
        video += f";[v0]subtitles={ass_tmp.name}:fontsdir={FONTES}[v]"
    else:
        video += ";[v0]null[v]"

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
        "-ss", f"{de_s:.3f}", "-t", f"{ate_s - de_s:.3f}", "-i", str(midia.resolve()),
        "-filter_complex", video, "-map", "[v]", "-map", "0:a:0?",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(qualidade),
        "-r", "30", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        # +faststart: o Instagram baixa o arquivo e precisa do índice no começo.
        # Sem isso o reel sobe e falha no processamento — lição de agosto.
        "-movflags", "+faststart", "-shortest", saida.name,
    ]
    try:
        subprocess.run(cmd, check=True, cwd=saida.parent)
    finally:
        if ass_tmp.exists():
            shutil.move(ass_tmp, ass_final)
    print(f"✓ {saida}  {inspecionar(saida)}", file=sys.stderr)
    return saida


def inspecionar(arquivo) -> str:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate:format=duration,size",
         "-of", "json", str(arquivo)],
        capture_output=True, text=True, check=True,
    )
    d = json.loads(r.stdout)
    s, f = d["streams"][0], d["format"]
    return (f"{s['width']}x{s['height']} {s['r_frame_rate']}fps "
            f"{float(f['duration']):.1f}s {int(f['size'])/1e6:.1f} MB")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transcrever", help="tempo de cada palavra → .palavras.json")
    t.add_argument("midia")
    t.add_argument("--modelo", default="small",
                   help="tiny|base|small|medium|large-v3 (padrão small)")
    t.add_argument("--idioma", default="pt")
    t.add_argument("--saida")
    t.add_argument("--de", help="só um trecho (para legenda final com modelo grande)")
    t.add_argument("--ate")

    l = sub.add_parser("ler", help="a transcrição com relógio, para escolher")
    l.add_argument("palavras")
    l.add_argument("--janela", type=float, default=45)

    c = sub.add_parser("cortar", help="recorta um reel 9:16 legendado")
    c.add_argument("midia")
    c.add_argument("--de", required=True, help="mm:ss ou h:mm:ss.s")
    c.add_argument("--ate", required=True)
    c.add_argument("--saida", required=True)
    c.add_argument("--palavras", help=".palavras.json (sem ele, sem legenda)")
    c.add_argument("--modo", default="moldura", choices=["moldura", "recorte"])
    c.add_argument("--foco", default="auto",
                   help="auto (segue quem fala) ou 0.0–1.0 fixo (padrão auto)")
    c.add_argument("--titulo")
    c.add_argument("--crf", type=int, default=18)
    c.add_argument("--tarja", default="auto", choices=["auto", "sim", "nao"],
                   help="recorte: há tarja de TV embaixo a cortar fora? (padrão auto)")

    a = ap.parse_args(argv)
    if a.cmd == "transcrever":
        transcrever(a.midia, modelo=a.modelo, idioma=a.idioma, saida=a.saida,
                    de=a.de, ate=a.ate)
    elif a.cmd == "ler":
        ler(a.palavras, janela=a.janela)
    elif a.cmd == "cortar":
        cortar(a.midia, a.de, a.ate, a.saida, palavras=a.palavras, modo=a.modo,
               foco=a.foco, titulo=a.titulo, qualidade=a.crf,
               barra={"auto": "auto", "sim": True, "nao": False}[a.tarja])


if __name__ == "__main__":
    main()
