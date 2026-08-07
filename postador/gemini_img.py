"""
gemini_img.py — Gera fundos com o Nano Banana (Gemini) da Google.

Por que isso e não crédito de Higgsfield: o Nano Banana Pro custa ~US$0,134 por
imagem em 2K e US$0,24 em 4K. Os 4 cards do mês saem por meio dólar. O
Higgsfield fica reservado para VÍDEO, que é onde ele é insubstituível.

Chave grátis em https://aistudio.google.com/apikey → GEMINI_API_KEY no .env.

    ./.venv/bin/python -m modules.gemini_img --modelos       # o que a chave alcança
    ./.venv/bin/python -m modules.gemini_img --teste         # gera uma imagem
"""
import base64
import os
from pathlib import Path

import requests

from .projeto import raiz
RAIZ = raiz()

try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

BASE = "https://generativelanguage.googleapis.com/v1beta"

# Nano Banana Pro para os fundos-herói; o Flash para volume e rascunho.
MODELO_PRO = "gemini-3-pro-image-preview"
MODELO_FLASH = "gemini-3.1-flash-image"

# Direção de arte fixa: entra em toda geração para o feed não virar colcha de
# retalhos. Sem gente identificável, sem texto — o texto é o nosso render.
ESTILO = (
    "cinematic photography, reverent and solemn atmosphere, volumetric light, "
    "deep shadows, rich gold and deep crimson accents, muted desaturated base, "
    "shot on 85mm, shallow depth of field, no text, no watermark, "
    "no identifiable faces, timeless — nothing modern in frame"
)


class GeminiErro(RuntimeError):
    pass


def _chave():
    k = os.getenv("GEMINI_API_KEY", "").strip()
    if not k:
        raise GeminiErro(
            "GEMINI_API_KEY não definida. Pegue em https://aistudio.google.com/apikey"
        )
    return k


def modelos():
    """Lista o que a chave realmente alcança — os nomes mudam com frequência."""
    r = requests.get(f"{BASE}/models", headers={"x-goog-api-key": _chave()}, timeout=40)
    r.raise_for_status()
    achados = []
    for m in r.json().get("models", []):
        nome = m.get("name", "").replace("models/", "")
        if "image" in nome:
            achados.append((nome, m.get("description", "")[:70]))
    return achados


def gerar(prompt, saida, formato="4:5", tamanho="2K", modelo=MODELO_PRO,
          com_estilo=True):
    """Gera uma imagem e grava em `saida`."""
    texto = f"{prompt}. {ESTILO}" if com_estilo else prompt
    corpo = {
        "model": modelo,
        "input": [{"type": "text", "text": texto}],
        "response_format": {
            "type": "image",
            "mime_type": "image/jpeg",
            "aspect_ratio": formato,
            "image_size": tamanho,
        },
    }
    r = requests.post(f"{BASE}/interactions",
                      headers={"x-goog-api-key": _chave(),
                               "Content-Type": "application/json"},
                      json=corpo, timeout=180)
    if not r.ok:
        detalhe = r.text[:400]
        if r.status_code == 404:
            detalhe += ("\n\n→ Modelo não encontrado. Rode --modelos para ver "
                        "os nomes que a sua chave alcança.")
        if r.status_code == 429:
            detalhe += ("\n\n→ Cota estourada. A geração de imagem costuma exigir "
                        "faturamento ativo no projeto do AI Studio.")
        raise GeminiErro(f"HTTP {r.status_code}: {detalhe}")

    dados = r.json()
    b64 = (dados.get("output_image") or {}).get("data")
    if not b64:  # formatos alternativos de resposta
        for parte in dados.get("output", []) or []:
            if isinstance(parte, dict) and parte.get("type") == "image":
                b64 = parte.get("data") or (parte.get("image") or {}).get("data")
                if b64:
                    break
    if not b64:
        raise GeminiErro(f"resposta sem imagem: {str(dados)[:400]}")

    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_bytes(base64.b64decode(b64))

    if tem_marca_visivel(saida):
        print(f"⚠️  {saida.name}: possível marca d'água no canto inferior "
              "direito. Rode com --sem-marca para cortar.")
    return saida


def tem_marca_visivel(caminho, limiar=0.09):
    """A SynthID que a Google embute é invisível e não incomoda. O que
    incomoda é o selo VISÍVEL que aparece no nível gratuito. Este teste olha
    o canto inferior direito e avisa se houver algo claro e destacado ali."""
    from PIL import Image, ImageStat
    im = Image.open(caminho).convert("L")
    w, h = im.size
    canto = im.crop((int(w * 0.72), int(h * 0.92), w, h))
    resto = im.crop((0, int(h * 0.92), int(w * 0.72), h))
    if ImageStat.Stat(resto).stddev[0] < 1:
        return False
    return (ImageStat.Stat(canto).stddev[0] /
            max(1e-6, ImageStat.Stat(resto).stddev[0])) > 1 + limiar * 10


def cortar_marca(caminho, fracao=0.055):
    """Remove a faixa de baixo. Como a imagem é fundo (entra desfocada, com
    névoa e vinheta por cima), perder 5% do rodapé não faz falta."""
    from PIL import Image
    im = Image.open(caminho)
    im.crop((0, 0, im.width, int(im.height * (1 - fracao)))).save(
        caminho, quality=95, subsampling=0)
    return caminho


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", action="store_true")
    ap.add_argument("--teste", action="store_true")
    ap.add_argument("--prompt", default="An ancient masonic temple interior, "
                    "empty, shafts of morning light through high windows, "
                    "checkered marble floor receding into shadow")
    ap.add_argument("--modelo", default=MODELO_PRO)
    ap.add_argument("--sem-marca", action="store_true",
                    help="corta 5%% do rodapé, onde a marca visível aparece")
    a = ap.parse_args()

    if a.modelos:
        for nome, desc in modelos():
            print(f"  {nome:42} {desc}")
    elif a.teste:
        p = gerar(a.prompt, RAIZ / "IMAGENS POST" / "teste-gemini.jpg",
                  modelo=a.modelo)
        if a.sem_marca:
            cortar_marca(p)
        print("✅", p)
    else:
        ap.print_help()
