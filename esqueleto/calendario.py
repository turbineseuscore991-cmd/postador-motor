"""Atalho para o motor. O código está em postador-motor/postador/calendario.py"""
import sys

import _motor
_motor.carregar()

from postador.calendario import *          # noqa: F401,F403,E402
from postador import calendario as _mod    # noqa: E402

if __name__ == "__main__":
    sys.exit(_mod.main() or 0)
