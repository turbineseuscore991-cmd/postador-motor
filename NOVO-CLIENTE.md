# Como nasce um cliente novo

Leia isto antes de criar qualquer pasta. São 10 minutos e evitam os erros que
já custaram post errado no ar.

## A regra que explica tudo

**Uma pasta por cliente, ao lado do motor.** Nunca dentro de outro cliente.

```
Documents/
  postador-motor/     este repositório — o maquinário, compartilhado
  arcoreal-bot/       cliente
  lastrom-bot/        cliente
  rabino-bot/         cliente
```

Cada pasta tem seu `.env`, suas fotos, seu `CLAUDE.md` e suas regras. Nenhuma
sabe da outra. É isso que impede a regra de um cliente de vazar para o post de
outro — e impede que um erro derrube todos.

**Abrir a conversa na pasta certa é o passo mais importante.** O `CLAUDE.md`
da pasta carrega sozinho. Abrir na pasta do Arco Real e pedir um post do
rabino faz o Claude aplicar as regras do Rito ao rabino. Já aconteceu.

## Os passos

### 1. Copiar o esqueleto

```bash
cp -R ~/Documents/postador-motor/esqueleto ~/Documents/<cliente>-bot
cd ~/Documents/<cliente>-bot
python3 -m venv .venv && ./.venv/bin/pip install requests Pillow python-dotenv
```

### 2. Preencher `marca.py`

Trocar **todos** os valores. Os que mais quebram se ficarem do exemplo:

| campo | por que importa |
|---|---|
| `CHAVE` | único por cliente. Repetido, dois painéis embaralham as aprovações e o post de um sai com a decisão do outro |
| `REDES` | `("facebook",)` para quem só tem página. Sem isso o robô tenta um Instagram que não existe e falha sempre |
| `REPO_MIDIA` | é de onde a Meta **baixa** a arte. Um por cliente |
| `AGENTE` | nome do serviço no macOS. Repetido, instalar o segundo vigia desinstala o primeiro |

### 3. Escrever o `CLAUDE.md`

O que o cliente faz, **quem lê**, as regras invioláveis e — se houver doutrina
ou norma técnica — **quem revisa antes de publicar**.

### 4. O logo

`assets/img/logo_0.png`, com fundo transparente. **É do cliente, não do
motor.** Se faltar, o render usa o do motor e a arte sai com a marca errada —
bonita, e ninguém percebe até estar publicada.

### 5. Repositório de mídia

Criar público, com Pages ligado. A Meta não recebe upload: ela baixa de um
endereço público.

```bash
gh repo create <cliente>-midia --public
# ligar o Pages em Settings → Pages → branch main
```

### 6. Credenciais

`.env` local e os mesmos nomes como Secrets no repositório do cliente:

```
META_TOKEN=          token da Página
META_USER_TOKEN=     token de usuário, para renovar sozinho quando cair
IG_USER_ID=          só se publicar no Instagram
FB_PAGE_ID=          só se publicar no Facebook
MIDIA_BASE_URL=      https://<usuario>.github.io/<cliente>-midia
TELEGRAM_BOT_TOKEN=  avisos e perguntas
TELEGRAM_CHAT_ID=
```

### 7. Ajustar o cron

`.github/workflows/publicar.yml` vem com as faixas do Arco Real. Trocar pelas
do cliente **e espelhar em `plano.JANELAS`** — mudou um, mude o outro, senão o
post é aceito na validação e some sem publicar.

Lembrar que o cron é **UTC**: Brasília é UTC−3, então 6h daqui é 09:00 lá.

### 8. Conferir antes do primeiro post

```bash
./.venv/bin/python montar.py                 # valida, renderiza e hospeda
./.venv/bin/python saude.py                  # token, hospedagem, aprovações
./.venv/bin/python publicar.py --simular     # o que faria
./.venv/bin/python hospedar.py --conferir    # byte a byte
```

## Armadilhas que já custaram caro

Estão comentadas no código do motor. Em resumo:

- **A Meta BAIXA, não recebe.** Arte renderizada e não hospedada morre com
  `9004 Only photo or video can be accepted`. Por isso o `montar.py` hospeda
  no mesmo passo
- **Reel: conferir o endereço público, não o disco.** O `.gitignore` exclui
  `reels/*.mp4`, então o robô baixa o repositório sem o vídeo
- **Cron de alta frequência é estrangulado** pelo GitHub em repo privado.
  De hora em hora entrega ~100%; de 20 em 20 minutos caiu para ~25%
- **Log do vigia dentro do projeto quebra o agente.** O macOS marca o arquivo
  com `com.apple.macl` e o launchd não consegue abri-lo. Por isso vai em
  `~/Library/Logs/`
- **Post que afirma doutrina ou norma técnica** vai para revisão de quem
  entende, antes de aprovar

## Custos

Os **2.000 minutos/mês grátis do GitHub Actions são da CONTA**, não do
repositório — todos os clientes dividem. Um cliente de hora em hora em três
faixas gasta ~330 min/mês. Passando dos 2.000, o excedente custa
US$ 0,006/min. Avisar antes de chegar lá.
