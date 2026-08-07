"""
postador — o motor de postagem, compartilhado entre clientes.

Este pacote não sabe de nenhuma marca. Quem sabe é a pasta do cliente, que
traz dois arquivos:

    plano.py   o calendário e as regras editoriais (validar() é o portão)
    marca.py   nome, @, logo, pasta de fotos, repositório de mídia

O motor lê os dois a partir do diretório de onde o comando foi chamado. Rode
sempre de dentro da pasta do cliente:

    cd ~/Documents/arcoreal-bot
    ./.venv/bin/python -m postador.montar
    ./.venv/bin/python -m postador.publicar --simular

Rodar de fora dá erro explicando — em vez de gerar um painel vazio, que é o
tipo de falha silenciosa que já custou post fora do ar aqui.
"""
__version__ = "1.0.0"
