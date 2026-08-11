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
    meses = meses_a_mostrar(por_dia)
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

def meses_a_mostrar(por_dia):
    """Do mês corrente (ou do primeiro post) até dezembro.

    Só os meses com post escondiam justamente o que o Luiz quer ver: os vazios.
    Um mês inteiro em branco é informação, não desperdício de tela.
    """
    hoje = date.today()
    com_post = sorted({d[:7] for d in por_dia})
    inicio = min(com_post[0], f"{hoje:%Y-%m}") if com_post else f"{hoje:%Y-%m}"
    ano, mes = int(inicio[:4]), int(inicio[5:7])
    saida = []
    while (ano, mes) <= (hoje.year, 12):
        saida.append(f"{ano:04d}-{mes:02d}")
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
    return saida


def montar_html(por_dia) -> str:
    hoje = date.today()
    meses = meses_a_mostrar(por_dia)
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
<html lang="pt-BR" data-tema="creme"><head><meta charset="utf-8">
<title>Calendário · {marca.NOME}</title>
<style>
/* Três temas. O seletor grava a escolha no navegador e ela volta sozinha
   na próxima vez — sem mexer em código nem regerar o arquivo. */
[data-tema="escuro"]{{
  --fundo:#0d0d10; --papel:#17171c; --vazio:#111116; --borda:#26262e;
  --texto:#e8e8ea; --fraco:#8a8a92; --hoje:#d4a24a;
  --pub-f:#153d24; --pub-t:#7ee2a0;
  --apr-f:#14304d; --apr-t:#7cc0f5;
  --pen-f:#4a3410; --pen-t:#f0c274;
}}
/* o padrão, pedido pelo Luiz: fundo creme e quadrados azul-marinho */
:root, [data-tema="creme"]{{
  --fundo:#f7f3e8; --papel:#1b2f4b; --vazio:#efe7d4; --borda:#d6c9ab;
  --texto:#2a2418; --fraco:#6f6450; --hoje:#b8860b;
  --pub-f:#1f5c3a; --pub-t:#b8f0cd;
  --apr-f:#2a4a75; --apr-t:#cfe4ff;
  --pen-f:#8a5a12; --pen-t:#ffe0a8;
}}
/* dentro do quadrado azul, o número do dia precisa clarear */
[data-tema="creme"] .n{{color:#9fb4d0}}
[data-tema="creme"] td.vazio .n{{color:#8c8069}}
[data-tema="claro"]{{
  --fundo:#f4f4f6; --papel:#ffffff; --vazio:#ececf0; --borda:#d8d8de;
  --texto:#1a1a1e; --fraco:#6a6a72; --hoje:#a9761b;
  --pub-f:#d8f0e0; --pub-t:#1c6b3a;
  --apr-f:#d9e8f8; --apr-t:#1a5590;
  --pen-f:#fbeacd; --pen-t:#8a5a0b;
}}
/* Azul profundo: fundo claro e frio, quadrados em azul-marinho fechado.
   O tema "azul" tinha fundo escuro TAMBÉM azul, e o quadrado sumia dentro
   dele. Aqui o contraste é o assunto: papel claro, dia bem escuro. */
[data-tema="profundo"]{{
  --fundo:#eef2f7; --papel:#12233d; --vazio:#e2e8f1; --borda:#c6d2e2;
  --texto:#16202e; --fraco:#5c6b7f; --hoje:#1f6fb8;
  --pub-f:#17543a; --pub-t:#9fecc5;
  --apr-f:#1d4a7d; --apr-t:#b8daff;
  --pen-f:#7a4f0e; --pen-t:#ffdb9c;
}}
[data-tema="profundo"] .n{{color:#93a9c6}}
[data-tema="profundo"] td.vazio .n{{color:#77869b}}
[data-tema="azul"]{{
  --fundo:#0a1420; --papel:#122236; --vazio:#0e1a29; --borda:#1e3550;
  --texto:#e3edf8; --fraco:#7f9ab5; --hoje:#4fb0e8;
  --pub-f:#0f3a2c; --pub-t:#6fe0b4;
  --apr-f:#14406b; --apr-t:#8fcaff;
  --pen-f:#4a3a12; --pen-t:#f2cc7a;
}}
*{{box-sizing:border-box}}
body{{margin:0;padding:32px;background:var(--fundo);color:var(--texto);
 font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
 transition:background .18s,color .18s}}
h1{{font-size:22px;margin:0 0 4px}}
h1 span{{color:var(--fraco);font-weight:400}}
.topo{{display:flex;justify-content:space-between;align-items:flex-start;
 flex-wrap:wrap;gap:14px}}
.resumo{{color:var(--fraco);margin-bottom:28px;font-size:14px}}
.temas{{display:flex;gap:6px}}
.temas button{{background:var(--papel);color:var(--fraco);border:1px solid var(--borda);
 border-radius:7px;padding:6px 13px;font-size:12px;cursor:pointer;
 font-family:inherit;transition:.15s}}
.temas button:hover{{color:var(--texto)}}
.temas button[aria-pressed="true"]{{border-color:var(--hoje);color:var(--hoje)}}
h2{{font-size:17px;margin:34px 0 10px;text-transform:capitalize}}
h2 span{{color:var(--fraco);font-weight:400}}
table{{width:100%;border-collapse:separate;border-spacing:6px}}
th{{color:var(--fraco);font-size:11px;text-transform:uppercase;
 letter-spacing:.09em;font-weight:600;padding-bottom:4px}}
td{{width:14.28%;height:104px;vertical-align:top;border-radius:9px;
 background:var(--papel);padding:7px}}
td.fora{{background:transparent}}
td.vazio{{background:var(--vazio);border:1px dashed var(--borda)}}
td.hoje{{outline:2px solid var(--hoje);outline-offset:1px}}
.n{{font-size:12px;color:var(--fraco);font-weight:600}}
td.hoje .n{{color:var(--hoje)}}
.p{{margin-top:5px;padding:4px 6px;border-radius:5px;font-size:11px;
 line-height:1.3;overflow:hidden}}
.p b{{display:block;font-size:10px;opacity:.8}}
.publicado{{background:var(--pub-f);color:var(--pub-t)}}
.aprovado{{background:var(--apr-f);color:var(--apr-t)}}
.pendente{{background:var(--pen-f);color:var(--pen-t)}}
.leg{{margin-top:26px;display:flex;gap:18px;font-size:12px;color:var(--fraco);
 flex-wrap:wrap}}
.leg i{{display:inline-block;width:9px;height:9px;border-radius:2px;
 margin-right:5px;vertical-align:middle;font-style:normal}}
@media print{{.temas{{display:none}}}}
</style></head><body>
<div class="topo">
 <div>
  <h1>Calendário <span>· {marca.ARROBA}</span></h1>
  <div class="resumo">{total} posts no plano · <b>{pend}</b> ainda sem aprovação ·
   dia tracejado é dia vazio</div>
 </div>
 <div class="temas">
  <button data-t="creme">creme</button>
  <button data-t="claro">claro</button>
  <button data-t="escuro">escuro</button>
  <button data-t="azul">azul</button>
  <button data-t="profundo">azul profundo</button>
 </div>
</div>
{"".join(blocos)}
<div class="leg">
 <span><i style="background:var(--pub-f)"></i>publicado</span>
 <span><i style="background:var(--apr-f)"></i>aprovado, esperando a hora</span>
 <span><i style="background:var(--pen-f)"></i>falta aprovar</span>
 <span><i style="background:var(--vazio);border:1px dashed var(--borda)"></i>vazio</span>
</div>
<script>
const CHAVE = '{marca.CHAVE}_tema_calendario';
function aplicar(t) {{
  document.documentElement.dataset.tema = t;
  localStorage.setItem(CHAVE, t);
  document.querySelectorAll('.temas button').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.t === t));
}}
document.querySelectorAll('.temas button').forEach(b =>
  b.onclick = () => aplicar(b.dataset.t));
aplicar(localStorage.getItem(CHAVE) || 'creme');
</script>
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

    destino = RAIZ / "Painel"
    destino.mkdir(exist_ok=True)
    destino = destino / "calendario.html"
    destino.write_text(montar_html(por_dia), encoding="utf-8")
    print(f"✅ {destino.relative_to(RAIZ)}")
    webbrowser.open(f"file://{destino}")
    return 0
