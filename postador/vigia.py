"""
vigia.py — Recolhe as aprovações do painel sozinho, sem você fazer nada.

O painel roda no navegador e o navegador não escreve em arquivo do projeto.
Então, a cada aprovação, ele baixa um `aprovado.json` na pasta Downloads.
Este vigia fica de olho nessa pasta, recolhe o arquivo, junta com a fila e
envia ao GitHub — onde o robô enxerga.

Resultado: você aprova no painel e acabou. Sem botão, sem comando, sem terminal.

    ./.venv/bin/python vigia.py            # roda até você fechar
    ./.venv/bin/python vigia.py --uma-vez  # recolhe uma vez e sai
    ./.venv/bin/python vigia.py --instalar # roda sozinho sempre que o Mac liga
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .projeto import raiz
RAIZ = raiz()
sys.path.insert(0, str(RAIZ))

from . import bot  # noqa: E402

PY = RAIZ / ".venv" / "bin" / "python"
DOWNLOADS = Path.home() / "Downloads"
import marca   # do cliente

PLIST = (Path.home() / "Library" / "LaunchAgents"
         / f"{marca.AGENTE}.plist")
INTERVALO = 30


def tem_novidade() -> bool:
    return any(DOWNLOADS.glob("aprovado*.json"))


def recolher() -> bool:
    """Chama o aprovar.py, que já sabe juntar e enviar."""
    r = subprocess.run([str(PY), "aprovar.py"], cwd=RAIZ,
                       capture_output=True, text=True, timeout=300)
    saida = (r.stdout or "") + (r.stderr or "")
    if "Gravado em" in saida:
        for linha in saida.splitlines():
            if any(m in linha for m in ("✅", "✏️", "🚀", "⚠️")):
                print(f'  {linha.strip()}')
        return True
    return False


def responder_telegram(espera=0):
    """Responde o que o Luiz perguntou no bot, no próprio processo.

    Antes disparava um `bot.py` novo a cada 5 segundos. O Telegram trava
    consultas simultâneas com o mesmo token, então elas se atropelavam e o bot
    parecia congelado — uma consulta chegou a levar 41 segundos para devolver
    "nada novo". Agora é uma escuta longa só, aqui dentro.
    """
    try:
        n = bot.uma_rodada(espera=espera)
        if n:
            print(f'  💬 {n} recado(s) respondido(s)', flush=True)
    except Exception as e:
        print(f'  ❌ bot falhou: {type(e).__name__}: {e}', flush=True)


def instalar():
    """Registra no macOS para rodar sozinho, inclusive depois de reiniciar.

    Processo VIVO (`--escutar`) com KeepAlive, não um disparo a cada 30s: o
    modo anterior rodava, mas o bot do Telegram ficou mudo dois dias sem deixar
    rastro. Vivo, ele responde em segundos e o launchd reergue se morrer.
    """
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{marca.AGENTE}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{PY}</string>
    <string>{RAIZ / "vigia.py"}</string>
    <string>--escutar</string>
  </array>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>{RAIZ / "vigia.log"}</string>
  <key>StandardErrorPath</key><string>{RAIZ / "vigia.log"}</string>
  <key>WorkingDirectory</key><string>{RAIZ}</string>
</dict>
</plist>
""", encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
    r = subprocess.run(["launchctl", "load", str(PLIST)], capture_output=True, text=True)
    if r.returncode:
        print(f"❌ Não consegui instalar: {r.stderr[:200]}")
        return 1
    print("✅ Vigia instalado.\n")
    print(f"   Confere a pasta Downloads a cada {INTERVALO} segundos e envia")
    print("   as aprovações ao GitHub sozinho — inclusive depois de reiniciar.")
    print("\n   Para desligar:  ./.venv/bin/python vigia.py --desinstalar")
    return 0


def desinstalar():
    subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
    PLIST.unlink(missing_ok=True)
    print("✅ Vigia desligado.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uma-vez", action="store_true")
    ap.add_argument("--escutar", action="store_true",
                    help="fica vivo, recolhendo e respondendo (modo do launchd)")
    ap.add_argument("--instalar", action="store_true")
    ap.add_argument("--desinstalar", action="store_true")
    a = ap.parse_args()

    if a.instalar:
        return instalar()
    if a.desinstalar:
        return desinstalar()

    if a.uma_vez:
        if tem_novidade():
            print(f'[{datetime.now():%d/%m %H:%M}] aprovação nova recolhida')
            recolher()
        responder_telegram()
        return 0

    print(f"👀 Vigiando {DOWNLOADS} e escutando o Telegram (Ctrl+C para parar)",
          flush=True)
    try:
        while True:
            if tem_novidade():
                print(f'[{datetime.now():%H:%M:%S}] recolhendo…', flush=True)
                recolher()
            # escuta longa: devolve assim que chegar recado, ou após 25s.
            # é ela que faz as vezes do sleep — sem espera cega no meio.
            responder_telegram(espera=25)
    except KeyboardInterrupt:
        print("\nparei.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
