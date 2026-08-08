"""Atalho para o motor. O código de verdade está em postador-motor/postador/bot.py"""
import sys

import _motor
_motor.carregar()

from postador.bot import *          # noqa: F401,F403,E402
from postador import bot as _mod    # noqa: E402

if __name__ == "__main__":
    # propaga o código de saída: sem isso, falha do robô passa como sucesso
    # no GitHub Actions e o alerta nunca chega
    sys.exit(_mod.main() or 0)
