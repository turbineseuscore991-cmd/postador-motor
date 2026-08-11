"""
recebedor.py — Recebe as aprovações do painel SEM baixar arquivo.

O painel é um HTML aberto do disco (`file://`) e o navegador não escreve em
arquivo do projeto. A ponte era um download: cada aprovação largava um
`aprovado.json` em Downloads, o vigia recolhia. Funcionava, mas enchia a pasta
do Luiz — e, quando o vigia caía, a aprovação ficava presa lá sem ninguém
perceber. Foi assim que o post de 11/08 perdeu a hora.

Agora o vigia abre uma portinha em `localhost` e o painel manda a decisão
direto. Sem arquivo, sem pasta, sem intermediário.

**O download continua existindo como rede de segurança.** Se esta portinha não
responder — Mac desligado, vigia parado —, o painel volta a baixar sozinho.
Melhor um arquivo em Downloads do que uma aprovação perdida.

Só aceita conexão de `127.0.0.1`: nada que venha de fora da máquina entra.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORTA = 8787


def _fazer_handler(ao_receber):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            # o painel roda em file://, que o navegador manda como "null"
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            # o painel chama isto para saber se pode dispensar o download
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"vivo":true}')

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                dados = json.loads(self.rfile.read(n) or b"{}")
                quantos = ao_receber(dados)
                corpo = json.dumps({"ok": True, "recebidos": quantos}).encode()
                self.send_response(200)
            except Exception as e:
                corpo = json.dumps({"ok": False, "erro": str(e)[:200]}).encode()
                self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):
            pass      # o vigia já imprime o que interessa

    return Handler


def servir(ao_receber, porta=PORTA):
    """Sobe a portinha numa thread. Devolve o servidor, ou None se falhar.

    Nunca derruba o vigia: porta ocupada só significa voltar ao download.
    """
    try:
        srv = HTTPServer(("127.0.0.1", porta), _fazer_handler(ao_receber))
    except OSError as e:
        print(f"  ⚠️ porta {porta} ocupada ({e.errno}) — o painel segue baixando",
              flush=True)
        return None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"  🔌 recebendo aprovações em http://127.0.0.1:{porta}", flush=True)
    return srv
