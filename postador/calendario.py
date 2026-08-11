"""
calendario.py — Um mês de cada vez, para enxergar os buracos.

    ./.venv/bin/python calendario.py            # abre no navegador
    ./.venv/bin/python calendario.py --texto     # imprime no terminal

O painel de aprovação mostra os posts em fila; ótimo para decidir um por um,
péssimo para responder "que dias da semana que vem estão vazios?". Esta é a
outra vista: mês fechado, um quadradinho por dia.

Cada dia mostra o que tem, e a cor diz o estado:

    verde     publicado
    azul      aprovado, esperando a hora
    âmbar     falta aprovar
    cinza     vazio
"""
import argparse
import calendar
import json
import webbrowser
from datetime import date, datetime
from pathlib import Path

from .projeto import conferir, raiz

conferir()
import marca  # noqa: E402

RAIZ = raiz()
POSTS = RAIZ / "posts"

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _carregar(nome, padrao):
    arq = POSTS / nome
    if not arq.exists():
        return padrao
    return json.loads(arq.read_text(encoding="utf-8"))


def levantar():
    """Devolve {data: [post, …]} com o estado de cada um."""
    plano = _carregar("plano.json", [])
    feitos = _carregar("publicados.json", {})
    apr = _carregar("aprovado.json", {}).get("posts", {})

    por_dia = {}
    for p in plano:
        dia = p["quando"][:10]
        if p["id"] in feitos:
            estado = "publicado"
        elif apr.get(p["id"], {}).get("decisao") == "aprovado":
            estado = "aprovado"
        else:
            estado = "pendente"
        por_dia.setdefault(dia, []).append({
            "id": p["id"],
            "hora": p["quando"][11:16],
            "tipo": p["tipo"],
            "titulo": p.get("titulo") or p["corpo"][:40],
            "estado": estado,
        })
    for v in por_dia.values():
        v.sort(key=lambda x: x["hora"])
    return por_dia


# ---------------------------------------------------------------- terminal

CORES = {"publicado": "\033[32m●\033[0m", "aprovado": "\033[34m●\033[0m",
         "pendente": "\033[33m●\033[0m"}


def imprimir(por_dia):
    hoje = date.today()
    meses = sorted({d[:7] for d in por_dia})
    for ym in meses:
        ano, mes = int(ym[:4]), int(ym[5:7])
        print(f"\n  {MESES[mes-1].upper()} {ano}\n")
        print("  " + "  ".join(f"{d:^5}" for d in DIAS))
        for semana in calendar.Calendar(0).monthdatescalendar(ano, mes):
            linha, detalhe = [], []
            for d in semana:
                if d.month != mes:
                    linha.append("     ")
                    continue
                itens = por_dia.get(d.isoformat(), [])
                marcas = "".join(CORES[i["estado"]] for i in itens[:3])
                num = f"{d.day:2}"
                if d == hoje:
                    num = f"\033[1;7m{d.day:2}\033[0m"
                linha.append(f"{num}{marcas:<3}")
                for i in itens:
                    detalhe.append(f'       {d.day:2}/{mes:02} {i["hora"]} '
                                   f'{CORES[i["estado"]]} {i["id"]} {i["titulo"][:38]}')
            print("  " + "  ".join(f"{c:^5}" for c in linha))
            for l in detalhe:
                print(l)
    print(f'\n  {CORES["publicado"]} publicado   {CORES["aprovado"]} aprovado   '
          f'{CORES["pendente"]} falta aprovar\n')


# -------------------------------------------------------------------- html

def montar_html(por_dia) -> str:
    hoje = date.today()
    meses = sorted({d[:7] for d in por_dia})
    blocos = []
    for ym in meses:
        ano, mes = int(ym[:4]), int(ym[5:7])
        semanas = []
        for semana in calendar.Calendar(0).monthdatescalendar(ano, mes):
            celulas = []
            for d in semana:
                if d.month != mes:
                    celulas.append('<td class="fora"></td>')
                    continue
                itens = por_dia.get(d.isoformat(), [])
                hoje_cls = " hoje" if d == hoje else ""
                vazio = " vazio" if not itens else ""
                pastilhas = "".join(
                    f'<div class="p {i["estado"]}" title="{i["id"]} · {i["tipo"]}">'
                    f'<b>{i["hora"]}</b> {i["titulo"][:30]}</div>' for i in itens)
                celulas.append(
                    f'<td class="dia{hoje_cls}{vazio}">'
                    f'<span class="n">{d.day}</span>{pastilhas}</td>')
            semanas.append("<tr>" + "".join(celulas) + "</tr>")
        cab = "".join(f"<th>{d}</th>" for d in DIAS)
        blocos.append(f'<h2>{MESES[mes-1]} <span>{ano}</span></h2>'
                      f'<table><thead><tr>{cab}</tr></thead>'
                      f'<tbody>{"".join(semanas)}</tbody></table>')

    total = sum(len(v) for v in por_dia.values())
    pend = sum(1 for v in por_dia.values() for i in v if i["estado"] == "pendente")
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Calendário · {marca.NOME}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;padding:32px;background:#0d0d10;color:#e8e8ea;
 font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
h1{{font-size:22px;margin:0 0 4px}}
h1 span{{color:#8a8a92;font-weight:400}}
.resumo{{color:#8a8a92;margin-bottom:28px;font-size:14px}}
h2{{font-size:17px;margin:34px 0 10px;text-transform:capitalize}}
h2 span{{color:#8a8a92;font-weight:400}}
table{{width:100%;border-collapse:separate;border-spacing:6px}}
th{{color:#7a7a82;font-size:11px;text-transform:uppercase;
 letter-spacing:.09em;font-weight:600;padding-bottom:4px}}
td{{width:14.28%;height:104px;vertical-align:top;border-radius:9px;
 background:#17171c;padding:7px}}
td.fora{{background:transparent}}
td.vazio{{background:#111116;border:1px dashed #26262e}}
td.hoje{{outline:2px solid #d4a24a;outline-offset:1px}}
.n{{font-size:12px;color:#8a8a92;font-weight:600}}
td.hoje .n{{color:#d4a24a}}
.p{{margin-top:5px;padding:4px 6px;border-radius:5px;font-size:11px;
 line-height:1.3;overflow:hidden}}
.p b{{display:block;font-size:10px;opacity:.8}}
.publicado{{background:#153d24;color:#7ee2a0}}
.aprovado{{background:#14304d;color:#7cc0f5}}
.pendente{{background:#4a3410;color:#f0c274}}
.leg{{margin-top:26px;display:flex;gap:18px;font-size:12px;color:#8a8a92}}
.leg i{{display:inline-block;width:9px;height:9px;border-radius:2px;
 margin-right:5px;vertical-align:middle;font-style:normal}}
</style></head><body>
<h1>Calendário <span>· {marca.ARROBA}</span></h1>
<div class="resumo">{total} posts no plano · <b>{pend}</b> ainda sem aprovação ·
 dia tracejado é dia vazio</div>
{"".join(blocos)}
<div class="leg">
 <span><i style="background:#153d24"></i>publicado</span>
 <span><i style="background:#14304d"></i>aprovado, esperando a hora</span>
 <span><i style="background:#4a3410"></i>falta aprovar</span>
 <span><i style="background:#111116;border:1px dashed #26262e"></i>vazio</span>
</div>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texto", action="store_true",
                    help="imprime no terminal em vez de abrir o navegador")
    a = ap.parse_args()

    por_dia = levantar()
    if not por_dia:
        raise SystemExit("Nenhum post no plano. Rode: python montar.py")

    if a.texto:
        imprimir(por_dia)
        return 0

    destino = POSTS / "calendario.html"
    destino.write_text(montar_html(por_dia), encoding="utf-8")
    print(f"✅ {destino.relative_to(RAIZ)}")
    webbrowser.open(f"file://{destino}")
    return 0
