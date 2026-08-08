"""
marca.py — Tudo que é DESTE cliente e de mais ninguém.

O motor (`postador`) não sabe de marca nenhuma. Este arquivo é o que faz o
mesmo código publicar para um cliente e não para outro.

TROQUE TODOS OS VALORES ABAIXO. Deixar algo do exemplo faz o post sair com a
identidade errada — e sai bonito, então ninguém percebe até estar publicado.
"""

# ---------------------------------------------------------------- identidade
NOME = "Nome Curto"                  # aparece no título do painel
ARROBA = "@usuario"                  # vai impresso na arte, canto inferior
LOCAL = "São Paulo"

# Nome por extenso, para quando o corpo do post citar a instituição.
NOME_OFICIAL = "Nome Completo da Instituição"

# ------------------------------------------------------------------- redes
# Onde este cliente publica. Um só, ou os dois.
#     ("instagram", "facebook")   os dois
#     ("facebook",)               só página do Facebook
#     ("instagram",)              só Instagram
# Sem isto, o publicador tenta as duas e falha em quem não tem conta.
REDES = ("instagram", "facebook")

# --------------------------------------------------------------------- pastas
PASTA_FOTOS = "Fotos"                # onde ficam as fotos deste cliente

# ------------------------------------------------------------------ navegador
# Prefixo das chaves no navegador e nome do arquivo de log. Precisa ser ÚNICO
# por cliente: dois painéis abertos no mesmo navegador com a mesma chave
# embaralham as aprovações, e o post de um sai com a decisão do outro.
CHAVE = "cliente"

# ------------------------------------------------------------------ hospedagem
# Repositório PÚBLICO de onde a Meta baixa as artes — ela não aceita upload,
# ela BAIXA. Criar antes do primeiro post, com o GitHub Pages ligado.
# Um por cliente: misturar mídia de marcas diferentes num repo público expõe
# o calendário editorial de um para o outro.
REPO_MIDIA = "usuario/cliente-midia"
BASE_MIDIA = "https://usuario.github.io/cliente-midia"

# ----------------------------------------------------------------- agente local
# Nome do serviço no macOS. Único por cliente, senão instalar o vigia do
# segundo desinstala o do primeiro e as aprovações param sem aviso.
AGENTE = f"com.postador.{CHAVE}"

# ------------------------------------------------- regras para a IA do painel
# O que o assistente do painel precisa saber para escrever no tom certo.
# É o resumo; a validação de verdade está em plano.validar().
REGRAS = """\
1. Escreva para <quem é o público>. <O que ele valoriza e o que o afasta.>
2. Corpo com no máximo 200 caracteres e 2 emojis.
3. Exatamente 5 hashtags, na última linha.
4. NUNCA citar data: o post precisa servir em qualquer dia.
5. <Regra própria deste cliente — termos proibidos, tratamento, etc.>"""
