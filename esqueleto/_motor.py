"""
_motor.py — Acha o motor compartilhado.

O código que serve qualquer marca mora em `postador-motor/`, fora desta pasta.
Aqui ficam só as coisas do Arco Real: `plano.py`, `marca.py`, as fotos, o
`.env` e as artes.

Por que não instalar com pip: tentei, e o `.pth` do modo editável simplesmente
não é aplicado neste Python 3.14. Três linhas de `sys.path` sempre funcionam,
não dependem de rede, não quebram quando o venv é recriado e — o que mais
importa — deixam os comandos exatamente como sempre foram:

    ./.venv/bin/python montar.py

`POSTADOR_MOTOR` permite apontar para outro lugar (GitHub Actions, teste).
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PADRAO = AQUI.parent / "postador-motor"


def carregar():
    """Põe o motor no caminho de importação. Falha explicando se não achar."""
    motor = Path(os.getenv("POSTADOR_MOTOR", PADRAO)).expanduser().resolve()
    if not (motor / "postador" / "__init__.py").exists():
        raise SystemExit(
            f"Não achei o motor em {motor}\n"
            "  Ele deve ficar ao lado desta pasta, como postador-motor/.\n"
            "  Ou aponte com POSTADOR_MOTOR=/caminho/do/motor"
        )
    if str(motor) not in sys.path:
        sys.path.insert(0, str(motor))
    # a pasta do cliente também: é de onde saem `plano` e `marca`
    if str(AQUI) not in sys.path:
        sys.path.insert(0, str(AQUI))
    return motor
