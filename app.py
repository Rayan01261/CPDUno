from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma_chave_secreta_aqui'

socketio = SocketIO(app, cors_allowed_origins="*")

salas = {}

monte = []

def criar_baralho(qtd_baralhos):
    cores = ["Vermelho", "Azul", "Amarelo", "Verde"]
    
    # 1 '0' por cor
    cartas_por_cor = {"0": 1}
    
    # 2 de cada número (1 a 9) por cor
    for i in range(1, 10):
        cartas_por_cor[str(i)] = 2
        
    # 2 de cada carta de ação por cor
    cartas_por_cor["Bloqueio"] = 2
    cartas_por_cor["Inverter"] = 2
    cartas_por_cor["Comprar 2"] = 2

    baralho = []
    for cor in cores:
        for carta, qtd in cartas_por_cor.items():
            baralho.extend([f"{cor} {carta}"] * qtd)

    # 4 de cada coringa (sem cor)
    baralho.extend(["Comprar 4"] * 4)
    baralho.extend(["Coringa"] * 4)

    baralho = baralho * qtd_baralhos

    random.shuffle(baralho)
    return baralho


# ---------- Helpers de regra do jogo ----------

CORES = ["Vermelho", "Azul", "Amarelo", "Verde"]


def partes_carta(carta):
    """Separa 'Vermelho Bloqueio' em ('Vermelho', 'Bloqueio').
    Cartas curinga (Coringa / Comprar 4) não tem cor -> retorna (None, carta)."""
    for cor in CORES:
        if carta.startswith(cor + " "):
            return cor, carta[len(cor) + 1:]
    return None, carta


def eh_curinga(carta):
    return carta in ("Coringa", "Comprar 4")


def eh_carta_compra(carta):
    """+2 ou +4, usadas para empilhar penalidade."""
    return "Comprar 2" in carta or carta == "Comprar 4"


def pode_jogar_carta(sala, carta_jogada):
    if eh_curinga(carta_jogada):
        return True

    carta_mesa = sala['carta_atual']
    cor_mesa = cor_efetiva_mesa(sala)
    cor_jog, resto_jog = partes_carta(carta_jogada)

    if cor_mesa == cor_jog:
        return True

    if not eh_curinga(carta_mesa):
        _, resto_mesa = partes_carta(carta_mesa)
        if resto_mesa == resto_jog:
            return True

    return False


def cartas_jogaveis(sala, mao):
    if sala['compra_pendente'] > 0:
        return [c for c in mao if eh_carta_compra(c)]
    return [c for c in mao if pode_jogar_carta(sala, c)]


# ---------- Helpers de sala / turno ----------

def emitir_jogadores(room):
    if room not in salas:
        return
    jogadores = []
    for sid in salas[room]['jogadores']:
        jogadores.append({
            'sid': sid,
            'nome': salas[room]['nomes'].get(sid, 'Jogador'),
            'foto': salas[room].get('fotos', {}).get(sid),   # NOVO
            'qtd_cartas': len(salas[room]['maos'].get(sid, []))
        })
    emit('atualizar_jogadores', {'jogadores': jogadores}, room=room)


def jogador_da_vez(room):
    sala = salas.get(room)
    if not sala or not sala['jogadores']:
        return None
    indice = sala['turno_index'] % len(sala['jogadores'])
    return sala['jogadores'][indice]


def emitir_turno(room, passos=1):
    sid_vez = jogador_da_vez(room)
    if sid_vez is None:
        return
    sala = salas[room]
    nome_vez = sala['nomes'].get(sid_vez, 'Jogador')

    jogadores_sala = sala['jogadores']
    n = len(jogadores_sala)
    sid_prox = None
    nome_prox = None
    if n > 1:
        indice_atual = sala['turno_index'] % n
        indice_prox = (indice_atual + sala['direcao']) % n
        sid_prox = jogadores_sala[indice_prox]
        nome_prox = sala['nomes'].get(sid_prox, 'Jogador')

    emit('passar_turno', {
        'sid': sid_vez,
        'nome': nome_vez,
        'compra_pendente': sala.get('compra_pendente', 0),
        'direcao': sala.get('direcao', 1),
        'proximo_sid': sid_prox,
        'proximo_nome': nome_prox,
        'passos': passos          # <-- NOVO
    }, room=room)


def avancar_turno(room, pular=1):
    sala = salas.get(room)
    if not sala or not sala['jogadores']:
        return
    n = len(sala['jogadores'])
    sala['turno_index'] = (sala['turno_index'] + pular * sala['direcao']) % n
    emitir_turno(room, passos=pular)   # <-- passa o "pular" adiante


def emitir_carta_mesa(room):
    sala = salas.get(room)
    if not sala or not sala.get('carta_atual'):
        return
    emit('carta_mesa', {
        'carta': sala['carta_atual'],
        'cor': sala.get('cor_escolhida')
    }, room=room)


@app.route('/')
def index():
    return render_template('uno.html')


@socketio.on('connect')
def handle_connect():
    print('Cliente conectado:', request.sid)

@socketio.on('definir_foto')
def handle_definir_foto(data):
    room = data['sala']
    foto = data.get('foto')
    sid = request.sid

    sala = salas.get(room)
    if not sala or sid not in sala['jogadores']:
        return

    sala.setdefault('fotos', {})
    if foto:
        sala['fotos'][sid] = foto
    else:
        sala['fotos'].pop(sid, None)

    emitir_jogadores(room)



@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    for room in list(salas.keys()):
        sala = salas[room]
        if sid in sala['jogadores']:
            indice_saindo = sala['jogadores'].index(sid)
            sala['jogadores'].remove(sid)
            sala['nomes'].pop(sid, None)
            sala.setdefault('fotos', {}).pop(sid, None)   # NOVO
            sala['maos'].pop(sid, None)

            if sala['jogadores']:
                if indice_saindo < sala['turno_index']:
                    sala['turno_index'] -= 1
                sala['turno_index'] %= len(sala['jogadores'])

            emitir_jogadores(room)
            if sala['jogo_iniciado'] and sala['jogadores']:
                emitir_turno(room)
    print('Cliente desconectado:', sid)

@socketio.on('avisar_uno')
def handle_avisar_uno(data):
    room = data['sala']
    sid = request.sid
    sala = salas.get(room)
    if sala and sid in sala['jogadores']:
        emit('aviso_uno', {'msg': f'{sala["nomes"][sid]} está com UNO!'}, room=room)

@socketio.on('entrar_sala')
def handle_entrar_sala(data):
    room = data['sala']
    nome = (data.get('nome') or 'Jogador').strip()[:16]
    sid = request.sid
    join_room(room)

    if room in salas and salas[room]['jogo_iniciado']:
        emit('erro', {'msg': 'O jogo já começou nesta sala. Aguarde a próxima partida.'})
        return

    if room not in salas:
        salas[room] = {
            'jogadores': [],
            'nomes': {},
            'fotos': {},        # NOVO
            'baralho': [],
            'maos': {},
            'turno_index': 0,
            'monte': [],
            'direcao': 1,
            'compra_pendente': 0,
            'jogo_iniciado': False,
            'carta_atual': None,
            'cor_escolhida': None
        }

    if sid not in salas[room]['jogadores']:
        salas[room]['jogadores'].append(sid)
    salas[room]['nomes'][sid] = nome

    foto = data.get('foto')                     # NOVO
    if foto:                                     # NOVO
        salas[room]['fotos'][sid] = foto          # NOVO

    total_jogadores = len(salas[room]['jogadores'])

    emit('sala_entrada', {'msg': f'Você entrou na sala {room}. Total na sala: {total_jogadores}'})
    emit('status_sala', {'msg': f'{nome} entrou na sala. Total: {total_jogadores}'}, room=room)
    
    emitir_jogadores(room)
    socketio.emit('entregar_salas', {'salas': [
        {'nome': n, 'qtd_jogadores': len(s['jogadores']), 'jogo_iniciado': s['jogo_iniciado']}
        for n, s in salas.items()
    ]})

    if salas[room]['jogo_iniciado']:
        emitir_turno(room)

@socketio.on("salas_ativas")
def entregar_salas():
    resumo = []
    for nome_sala, sala in salas.items():
        resumo.append({
            'nome': nome_sala,
            'qtd_jogadores': len(sala['jogadores']),
            'jogo_iniciado': sala['jogo_iniciado']
        })
    emit('entregar_salas', {'salas': resumo})


@socketio.on('iniciar_jogo')
def iniciar_jogo(data):
    room = data['sala']

    if room not in salas or len(salas[room]['jogadores']) == 0:
        emit('erro', {'msg': 'Sala inválida ou vazia.'})
        return

    sala = salas[room]

    qtd_baralhos = 2 if len(sala['jogadores']) > 4 else 1
    sala['baralho'] = criar_baralho(qtd_baralhos)
    baralho = sala['baralho']

    for jogador_sid in sala['jogadores']:
        mao = [baralho.pop() for _ in range(7)]
        sala['maos'][jogador_sid] = mao
        emit('mao_inicial', {'mao': mao}, room=jogador_sid)

    # Abre a mesa com a primeira carta do baralho.
    # Se sair curinga, volta ela pro baralho e tira outra (evita começar sem cor de referência).
    primeira = baralho.pop()
    while eh_curinga(primeira) and baralho:
        baralho.insert(0, primeira)
        primeira = baralho.pop()
    sala['carta_atual'] = primeira
    sala['cor_escolhida'] = None   
    sala['turno_index'] = 0
    sala['direcao'] = 1
    sala['compra_pendente'] = 0
    sala['jogo_iniciado'] = True

    emit('jogo_iniciado', {'msg': 'Jogo iniciado com sucesso!'}, room=room)
    emitir_jogadores(room)
    emitir_carta_mesa(room)
    emitir_turno(room)


@socketio.on('play_log')
def handle_play_log(data):
    room = data['sala']
    msg = data['msg']
    emit('play_log', {'msg': msg}, room=room)

@socketio.on('tamanho_baralho')
def handle_tamanho_baralho(data):
    room = data['sala']
    sala = salas.get(room)
    if sala:
        emit('tamanho_baralho', {'tamanho': len(sala['baralho'])}, room=room)

@socketio.on('jogar_carta')
def handle_jogar_carta(data):
    room = data['sala']
    carta = data['carta']
    cor_escolhida = data.get('cor')  # NOVO: só relevante se for curinga
    sid = request.sid

    sala = salas.get(room)
    if not sala or sid not in sala['jogadores']:
        emit('erro', {'msg': 'Você não está nessa sala.'})
        return
    if not sala['jogo_iniciado']:
        emit('erro', {'msg': 'O jogo ainda não começou.'})
        return
    if jogador_da_vez(room) != sid:
        emit('erro', {'msg': 'Calma, ainda não é sua vez.'})
        return

    mao = sala['maos'].get(sid, [])
    if carta not in mao:
        emit('erro', {'msg': 'Você não tem essa carta na mão.'})
        return

    if eh_curinga(carta) and cor_escolhida not in CORES:
        emit('erro', {'msg': 'Escolha uma cor válida para essa carta.'})
        return

    if sala['compra_pendente'] > 0:
        if not eh_carta_compra(carta):
            emit('erro', {'msg': f'Tem uma compra pendente de {sala["compra_pendente"]} cartas! Só dá pra jogar +2 ou +4.'})
            return
    else:
        if not pode_jogar_carta(sala, carta):
            emit('erro', {'msg': 'Essa carta não combina com a carta da mesa.'})
            return

    mao.remove(carta)
    sala.setdefault('monte', []).append(carta)   # troque monte.append(carta) por isto
    sala['maos'][sid] = mao
    sala['carta_atual'] = carta
    sala['cor_escolhida'] = cor_escolhida if eh_curinga(carta) else None  # NOVO

    if len(mao) == 1:
        emit('avisar_uno', {'msg': f'{sala["nomes"][sid]} está com UNO!', 'nome': sala['nomes'][sid], 'sid': sid}, room=room)

    cor_carta, resto_carta = partes_carta(carta)
    if cor_carta:
        msg_log = f'{sala["nomes"][sid]} jogou {resto_carta} da cor {cor_carta}.'
    else:
        sufixo_cor = f' e escolheu a cor {cor_escolhida}' if cor_escolhida else ''
        msg_log = f'{sala["nomes"][sid]} jogou {carta}{sufixo_cor}.'

    emit('carta_jogada', {'carta': carta, 'jogador': sala['nomes'][sid], 'sid': sid}, room=room)
    emit('play_log', {'msg': msg_log}, room=room)
    
    emitir_jogadores(room)
    emitir_carta_mesa(room)

    if len(mao) == 0:
        emit('vencedor', {'msg': f'{sala["nomes"][sid]} venceu!', 'sid': sid}, room=room)  # <-- adicionado 'sid'
        sala['jogo_iniciado'] = False
        sala['maos'] = {}
        emitir_jogadores(room)
        return

    _, resto = partes_carta(carta)
    pular = 1



    if resto == "Bloqueio":
        pular = 2
    elif resto == "Inverter":
        sala['direcao'] *= -1
        if len(sala['jogadores']) == 2:
            pular = 2
    elif "Comprar 2" in carta:
        sala['compra_pendente'] += 2
    elif carta == "Comprar 4":
        sala['compra_pendente'] += 4

    print(len(sala['baralho']))

    avancar_turno(room, pular)

def cor_efetiva_mesa(sala):
    """Cor que vale pra bater, mesmo quando a carta da mesa é curinga."""
    carta_mesa = sala['carta_atual']
    if eh_curinga(carta_mesa):
        return sala.get('cor_escolhida')
    cor, _ = partes_carta(carta_mesa)
    return cor

@socketio.on('mudar_nome')
def handle_mudar_nome(data):
    room = data['sala']
    novo_nome = (data.get('nome') or '').strip()[:16]
    sid = request.sid

    sala = salas.get(room)
    if not sala or sid not in sala['jogadores']:
        emit('erro', {'msg': 'Você não está nessa sala.'})
        return

    if not novo_nome:
        emit('erro', {'msg': 'Digite um nome válido.'})
        return

    nome_antigo = sala['nomes'].get(sid, 'Jogador')
    if novo_nome == nome_antigo:
        return

    sala['nomes'][sid] = novo_nome
    emit('nome_atualizado', {'sid': sid, 'nome': novo_nome}, room=room)
    emit('play_log', {'msg': f'{nome_antigo} agora se chama {novo_nome}.'}, room=room)
    emitir_jogadores(room)

    # se for a vez dele, reemite o turno pra atualizar o "Turno de: X" na tela de todo mundo
    if sala['jogo_iniciado'] and jogador_da_vez(room) == sid:
        emitir_turno(room, passos=0)

def repor_baralho_se_vazio(sala):
    """Se o baralho esgotar, embaralha o monte de descarte de volta pra ele."""
    if sala['baralho']:
        return
    monte = sala.get('monte', [])
    if len(monte) <= 1:
        return  # não tem o suficiente pra repor (mantém a carta_atual fora)
    carta_topo = sala['carta_atual']
    novas = monte[:]  # tudo que foi descartado, exceto a carta atual da mesa
    if carta_topo in novas:
        novas.remove(carta_topo)
    random.shuffle(novas)
    sala['baralho'] = novas
    sala['monte'] = []

@socketio.on('sacar_carta')
def sacar_carta(data):
    room = data['sala']
    sid = request.sid

    sala = salas.get(room)
    if not sala or sid not in sala['jogadores']:
        emit('erro', {'msg': 'Você não está nessa sala.'})
        return
    if not sala['jogo_iniciado']:
        emit('erro', {'msg': 'O jogo ainda não começou.'})
        return
    if jogador_da_vez(room) != sid:
        emit('erro', {'msg': 'Calma, ainda não é sua vez.'})
        return

    mao = sala['maos'].setdefault(sid, [])

    # Caso 1: penalidade pendente (+2 / +4)
    if sala['compra_pendente'] > 0:
        empilhaveis = [c for c in mao if eh_carta_compra(c)]
        if empilhaveis:
            emit('erro', {'msg': 'Você tem uma carta +2/+4! Jogue-a em vez de comprar.'})
            return

        qtd = sala['compra_pendente']
        compradas = []
        for _ in range(qtd):
            repor_baralho_se_vazio(sala)
            if not sala['baralho']:
                emit('sem_cartas')
                break
            carta = sala['baralho'].pop()
            mao.append(carta)
            compradas.append(carta)

        sala['compra_pendente'] = 0
        emit('cartas_compradas', {'cartas': compradas, 'motivo': 'penalidade'})
        emit('tamanho_baralho', {'tamanho': len(sala['baralho'])}, room=room)
        emit('play_log', {'msg': f'{sala["nomes"][sid]} comprou {qtd} cartas.'}, room=room)
        emitir_jogadores(room)
        avancar_turno(room)
        return

    # Caso 2: sem penalidade — só compra se não tiver carta jogável
    if cartas_jogaveis(sala, mao):
        emit('erro', {'msg': 'Você tem uma carta jogável na mão. Jogue-a em vez de comprar.'})
        return

    repor_baralho_se_vazio(sala)
    if not sala['baralho']:
        emit('sem_cartas')
        emit('tamanho_baralho', {'tamanho': 0}, room=room)
        avancar_turno(room)   # baralho acabou de vez, passa a vez pra não travar
        return

    carta = sala['baralho'].pop()
    mao.append(carta)

    emit('cartas_compradas', {'cartas': [carta], 'motivo': 'sem_jogada'})
    emit('play_log', {'msg': f'{sala["nomes"][sid]} comprou 1 carta.'}, room=room)
    emit('tamanho_baralho', {'tamanho': len(sala['baralho'])}, room=room)
    emitir_jogadores(room)
    # turno não avança: jogador comprou uma carta e agora deve jogá-la (ou não ter opção e o cliente decide)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5050, debug=True)