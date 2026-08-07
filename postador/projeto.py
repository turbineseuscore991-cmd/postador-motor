"""
projeto.py — Onde ficam os arquivos DO CLIENTE.

Antes cada módulo fazia `RAIZ = Path(__file__).resolve().parent`, porque o
código morava dentro da pasta do cliente. Agora o motor é compartilhado: se
continuasse assim, `RAIZ` apontaria para dentro do pacote instalado e o robô
do Arco Real leria o plano da Lastrom — ou de ninguém.

A raiz passa a ser **o diretório de onde o comando foi chamado**. Cada cliente
tem sua pasta com `plano.py`, `marca.py`, `.env`, `entrada/` e as fotos; roda
`python -m postador.montar` de dentro dela e o motor enxerga só aquilo.

`ARCOREAL_RAIZ` existe para o caso de precisar apontar para outra pasta sem
mudar de diretório — útil em teste e no GitHub Actions.
"""
import os
from pathlib import Path


def raiz() -> Path:
    """A pasta do cliente. Nunca a pasta do motor."""
    forcada = os.getenv("POSTADOR_RAIZ", "").strip()
    return Path(forcada).expanduser().resolve() if forcada else Path.cwd()


def conferir() -> Path:
    """Falha cedo e explicando, em vez de gerar post vazio.

    Sem isto, rodar de fora da pasta do cliente produz um plano de zero posts
    e um painel em branco — que é justamente o tipo de falha silenciosa que já
    custou post fora do ar aqui.
    """
    r = raiz()
    if not (r / "plano.py").exists():
        raise SystemExit(
            f"Não achei plano.py em {r}\n"
            "  O motor precisa rodar de dentro da pasta do cliente.\n"
            "  Ex.:  cd ~/Documents/arcoreal-bot && "
            "./.venv/bin/python -m postador.montar"
        )
    return r
