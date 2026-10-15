# CPDUNO

UNO multiplayer online que roda no navegador. O servidor em **Flask + Socket.IO** controla salas, baralho, turnos e regras; o front-end é uma única página HTML/JS com animações, sons e confete na vitória.

---

## Funcionalidades

- **Salas**: entre por nome de sala ou pela lista de salas ativas (salas com jogo em andamento ficam bloqueadas)
- **Multiplayer em tempo real** via WebSocket
- **Regras do UNO** validadas no servidor (cartas, cores, turnos, penalidades)
- **Foto de perfil**: o jogador escolhe uma imagem, que é redimensionada no navegador e exibida aos demais
- **Troca de nome** durante a partida
- **Roleta de turnos** e indicação da direção do jogo
- **Aviso de UNO** quando alguém fica com uma carta
- **Animações** de cartas indo para a mesa e sendo compradas
- **Sons** gerados com Web Audio API (jogar, comprar, sua vez, erro, vitória), com botão para silenciar
- **Tela de vitória** com confete e botão "Jogar novamente"
- Log de jogadas em tempo real

---

## Regras implementadas

- Cada jogador começa com **7 cartas**
- Baralho padrão: 0 a 9, Bloqueio, Inverter e Comprar 2 em 4 cores, mais Coringa e Comprar 4. Com **mais de 4 jogadores**, são usados **2 baralhos**
- A primeira carta da mesa nunca é coringa
- Só é possível jogar carta da mesma **cor** ou do mesmo **número/símbolo**. Coringas podem ser jogados a qualquer momento e exigem a escolha de uma cor
- **Bloqueio** pula o próximo jogador
- **Inverter** muda a direção (com 2 jogadores, funciona como bloqueio)
- **Comprar 2 / Comprar 4** acumulam penalidade: o próximo jogador só pode responder com outra carta de compra. Se não tiver, compra tudo de uma vez e perde a vez
- Sem carta jogável, o jogador compra do baralho. Se tiver uma carta jogável, o servidor não permite comprar
- Quando o baralho acaba, as cartas descartadas são **embaralhadas de volta**
- Vence quem **zerar a mão** primeiro

---

## Como funciona

```
Navegador (uno.html)  ◄── Socket.IO ──►  Flask-SocketIO (app.py)
  interface, animações,                   salas, baralho, mãos,
  sons, envio de ações                    validação de jogadas, turnos
```

O servidor é a autoridade do jogo: o cliente apenas envia ações (`jogar_carta`, `sacar_carta`) e o servidor valida, atualiza o estado e transmite o resultado a todos da sala.

---

## Requisitos

- Python 3.9+
- Navegador moderno

```bash
pip install flask flask-socketio
```

O front-end carrega **Socket.IO** e **canvas-confetti** por CDN, então os jogadores precisam de acesso à internet (ou hospede esses scripts localmente).

---

## Instalação e execução

```bash
git clone https://github.com/<seu-usuario>/cpduno.git
cd cpduno

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python app.py
```

O servidor sobe em `http://0.0.0.0:5050`. Para jogar em rede local, os outros jogadores acessam `http://<ip-do-servidor>:5050`.

---

## Estrutura do projeto

```
.
├── app.py
├── templates/
│   └── uno.html
├── requirements.txt
└── README.md
```

---

## Configuração

No `app.py`:

| Item | Descrição |
|---|---|
| `SECRET_KEY` | Troque o valor padrão antes de expor o servidor |
| `port` | Porta do servidor (padrão `5050`) |
| `debug=True` | Desative em produção |
| `cors_allowed_origins="*"` | Restrinja aos domínios usados em produção |

---

## Eventos Socket.IO

### Cliente → Servidor

| Evento | Payload | Descrição |
|---|---|---|
| `salas_ativas` | n/d | Pede a lista de salas |
| `entrar_sala` | `{sala, nome, foto?}` | Entra (ou cria) uma sala |
| `iniciar_jogo` | `{sala}` | Distribui as cartas e começa a partida |
| `jogar_carta` | `{sala, carta, cor?}` | Joga uma carta (`cor` obrigatória para coringas) |
| `sacar_carta` | `{sala}` | Compra carta(s) |
| `mudar_nome` | `{sala, nome}` | Altera o nome (máx. 16 caracteres) |
| `definir_foto` | `{sala, foto}` | Define ou remove a foto de perfil |
| `avisar_uno` | `{sala}` | Avisa que está com UNO |

### Servidor → Cliente

| Evento | Descrição |
|---|---|
| `entregar_salas` | Lista de salas, com quantidade de jogadores e status |
| `atualizar_jogadores` | Jogadores da sala, com nome, foto e quantidade de cartas |
| `mao_inicial` | Mão do jogador no início da partida |
| `carta_mesa` | Carta atual da mesa e cor escolhida |
| `carta_jogada` | Carta jogada e por quem |
| `cartas_compradas` | Cartas recebidas por quem comprou (`penalidade` ou `sem_jogada`) |
| `passar_turno` | Jogador da vez, próximo, direção e compra pendente |
| `tamanho_baralho` | Quantidade de cartas restantes no baralho |
| `play_log` | Mensagens do log de jogadas |
| `aviso_uno` | Alguém ficou com uma carta |
| `vencedor` | Fim da partida |
| `nome_atualizado` | Nome alterado |
| `erro` | Jogada inválida ou ação não permitida |

---

## Limitações conhecidas

- Todo o estado fica **em memória**: reiniciar o servidor encerra as partidas e salas.
- Quem sai da sala (desconecta) **perde a mão**; não há reconexão à partida.
- Não é possível entrar em uma sala com jogo em andamento.
- Não há desafio ao Comprar 4, pontuação acumulada nem "gritar UNO" com penalidade.
- As fotos de perfil trafegam como imagem em base64 pelo WebSocket.

---

## Ideias futuras

- Reconexão ao jogo em andamento
- Penalidade por esquecer de avisar UNO
- Placar entre partidas
- Bots para completar mesas
- Persistência de salas

---

