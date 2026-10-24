# postador — motor de postagem

Publica no Instagram e no Facebook. **Não sabe de nenhuma marca**: quem sabe é
a pasta do cliente, que traz dois arquivos.

    plano.py    o calendário e as regras editoriais. `validar()` é o portão
    marca.py    nome, @, logo, pasta de fotos, repositório de mídia

## Como um cliente usa

A pasta do cliente fica **ao lado** desta, com um `_motor.py` de três linhas e
atalhos com os nomes de sempre:

    ~/Documents/
      postador-motor/          este repositório
      arcoreal-bot/            cliente
      lastrom-bot/             cliente

    cd ~/Documents/arcoreal-bot
    ./.venv/bin/python montar.py

## O que é de quem

| fica no motor | fica no cliente |
|---|---|
| render, publicar, hospedar, painel | plano.py, marca.py |
| as fontes (Cinzel, Montserrat, Cormorant) | o logo |
| a lógica de validação | as regras da marca |
| o vigia e o bot do Telegram | os segredos (.env) |

## Cortes de podcast

`postador.cortes` transforma um trecho de vídeo longo em reel 9:16 com legenda
palavra a palavra (Montserrat, palavra falada em amarelo). Precisa de `ffmpeg`
com libass e de `pip install -e ".[cortes]"` para transcrever.

    python -m postador.cortes transcrever PODCAST.mp4        # 1x, demora
    python -m postador.cortes ler PODCAST.palavras.json      # escolher trechos
    python -m postador.cortes cortar PODCAST.mp4 --de 12:03 --ate 13:01 \
        --palavras PODCAST.palavras.json --saida cortes/corte1.mp4 --titulo "..."

Corrigir um defeito aqui conserta todos os clientes de uma vez. Foi por isso
que o motor saiu de dentro do Arco Real: as correções de agosto — `+faststart`
no reel, hospedagem automática, checagem do endereço público em vez do disco —
teriam que ser reaplicadas à mão em cada cópia.
