"""
clientes.py — Quem são os clientes do estúdio, para o bot saber roteirizar.

O Luiz usa **um só bot do Telegram** para os três clientes, na mesma janela,
e pergunta pelo nome: "status lastrom", "status bodes", "status arco real".

O problema que isto resolve não é de conveniência, é de corrida. Os três
workflows rodavam `bot.py` com o MESMO token, e o Telegram entrega cada
recado **uma vez só**: quem acordasse primeiro consumia a pergunta e
respondia — podendo ser o cliente errado. Pergunta sobre a Lastrom
respondida com os números do Arco Real é pior que pergunta sem resposta.

Agora só UM workflow escuta (o do Arco Real, que é o mais antigo e o que
nunca ficou sem rodar). Ele responde pelo cliente de casa lendo o disco, e
pelos outros dois lendo o `estado.json` que cada um publica no seu
repositório PÚBLICO de mídia — o mesmo de onde a Meta baixa as artes.

Por que o repositório de mídia e não a API do GitHub: os repositórios dos
bots são privados e exigiriam um token novo guardado em três lugares. O de
mídia já é público, cada cliente já escreve nele em toda publicação, e o
`estado.json` carrega só contagem e datas — **nunca legenda**, que é a única
coisa ali que ainda não é pública.
"""
import re
import unicodedata

# REFRESCAR_ESTADO — a limitação conhecida, e como levantá-la.
#
# O `estado.json` só é reescrito quando o Luiz roda `montar.py` no Mac. O
# runner do GitHub NÃO consegue: o token do workflow só vale no próprio
# repositório, e o de mídia é outro. Medido em 01/10:
#
#     não consegui clonar turbineseuscore991-cmd/bodes-midia:
#     gh: set the GH_TOKEN environment variable
#
# Enquanto isso, o bot cola a idade do resumo na resposta (ver `_idade` em
# bot.py) — número velho apresentado como atual é pior que número nenhum.
#
# Para levantar: um token clássico (ou fine-grained) com escrita nos três
# repositórios `*-midia`, guardado como secret `MIDIA_TOKEN` nos três
# repositórios de bot, e `hospedar.preparar()` clonando com ele. É a única
# peça que falta para o resumo se atualizar com o Mac desligado.

# A ordem importa: é a ordem em que o resumo geral aparece no Telegram.
CLIENTES = [
    {
        "chave": "arcoreal",
        "nome": "Sagrado Arco Real",
        "arroba": "@arcorealoficial",
        "base": "https://turbineseuscore991-cmd.github.io/arcoreal-midia",
        # Apelidos: como o Luiz escreve de fato, no celular, com pressa e
        # sem acento. "arco" sozinho basta porque nenhum outro cliente tem.
        #
        # "real" NÃO entra: casaria com "funcionou de verdade real" e toda
        # outra frase comum. Apelido que gera falso positivo é pior que
        # apelido que falta — o que falta o Luiz reescreve, o falso positivo
        # responde pelo cliente errado sem avisar.
        "apelidos": ["arco real", "arcoreal", "arco", "sagrado"],
    },
    {
        "chave": "lastrom",
        "nome": "Lastrom",
        "arroba": "@lastrom.br",
        "base": "https://turbineseuscore991-cmd.github.io/lastrom-midia",
        "apelidos": ["lastrom", "lastron", "rui"],
    },
    {
        "chave": "bodes",
        "nome": "Bodes Amantes de Charutos",
        "arroba": "@bodescharutos",
        "base": "https://turbineseuscore991-cmd.github.io/bodes-midia",
        # "bac" ficou de fora: casaria dentro de "bacana".
        "apelidos": ["bodes", "bode", "charuto", "charutos"],
    },
]

POR_CHAVE = {c["chave"]: c for c in CLIENTES}


def qual(texto: str):
    """Qual cliente esta pergunta nomeia? Devolve o registro, ou None.

    Casa por PALAVRA INTEIRA, não por pedaço: "bacana" não pode virar
    "bodes", e "realmente" não pode virar "arco real". Substring aqui
    responde pelo cliente errado sem avisar ninguém.

    Entre dois casamentos, ganha o apelido mais longo — "arco real" antes
    de "arco".
    """
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    achados = []
    for c in CLIENTES:
        for a in c["apelidos"]:
            if re.search(rf"(?<!\w){re.escape(a)}(?!\w)", t):
                achados.append((len(a), c))
    if not achados:
        return None
    achados.sort(key=lambda x: -x[0])
    return achados[0][1]
