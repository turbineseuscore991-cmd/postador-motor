"""Atalho para o motor. O código está em postador-motor/postador/configurar_meta.py"""
import sys

import _motor
_motor.carregar()

from postador.configurar_meta import *        # noqa: F401,F403,E402
from postador import configurar_meta as _mod  # noqa: E402

if __name__ == "__main__":
    sys.exit(_mod.main() or 0)
