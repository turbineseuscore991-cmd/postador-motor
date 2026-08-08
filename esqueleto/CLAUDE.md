# <CLIENTE> — postagem automática

> Este arquivo é lido sozinho toda vez que uma conversa abre NESTA pasta.
> Escreva aqui o que o Claude precisa saber para não errar. Troque tudo que
> estiver entre `<>`.

Publica em <Instagram / página do Facebook> de **<@perfil>**, <quem é o
cliente em uma frase>.

O motor fica em `../postador-motor/` e serve todos os clientes. **Aqui só o
que é deste.** Não misture: regra de um cliente aplicada em outro já colocou
informação errada no ar.

---

## Quem lê

<Descreva o público de verdade: quem é, o que valoriza, o que o afasta. É isso
que decide o tom. "Gerente de manutenção que aprova orçamento" e "fiel que
busca conforto" não se escrevem igual.>

## Regras invioláveis

Estão no `plano.validar()`, que roda antes de qualquer coisa ir ao ar. **Se
mexer numa regra, mexa lá** — não só no texto do post.

- Corpo com no máximo **200 caracteres** e **2 emojis**
- **Exatamente 5 hashtags**, na última linha (o Instagram trava em 5 desde
  dez/2025)
- **Nada de data.** O post precisa servir em qualquer dia
- **Nunca repetir** foto, fundo, legenda nem título
- <Termos obrigatórios e proibidos deste cliente>
- <Tratamento: como se chamam as pessoas, cargos, títulos>

## O que NÃO posso afirmar sozinho

<Se o cliente tem doutrina, norma técnica ou qualquer coisa que exija fonte,
escreva aqui e diga quem revisa. No Arco Real isso custou três correções e uma
locução refeita duas vezes.>

## Horários

O robô só acorda em: <faixas>. `plano.JANELAS` espelha o cron de
`.github/workflows/publicar.yml`. **Mudou um, mude o outro** — senão o post é
aceito e some calado.

## Comandos

```bash
./.venv/bin/python montar.py                 # valida, renderiza, painel e hospeda
./.venv/bin/python aprovar.py                # recolhe as aprovações do painel
./.venv/bin/python publicar.py --simular     # mostra o que faria
./.venv/bin/python publicar.py --forcar p01  # publica um post agora
./.venv/bin/python saude.py                  # diagnóstico
```

## Custos

Os 2.000 min/mês grátis do GitHub Actions são **da conta**, divididos entre
todos os clientes. Diga o gasto antes e depois — o Luiz já levou cobrança
surpresa e isso pesa.
