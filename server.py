import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Path, Query
from fastapi.responses import HTMLResponse
from typing import Dict, Optional, List
import logging

# Configuração
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Constantes do Jogo ---
BOARD_SIZE = 5
SHIP_COUNT = 5

# --- Validação (Idêntica a antes) ---
def validate_board(board: list) -> bool:
    try:
        if not (isinstance(board, list) and len(board) == BOARD_SIZE):
            return False
        total_ships = 0
        for row in board:
            if not (isinstance(row, list) and len(row) == BOARD_SIZE):
                return False
            for cell in row:
                if cell == 1:
                    total_ships += 1
                elif cell != 0:
                    return False
        return total_ships == SHIP_COUNT
    except Exception as e:
        logger.error(f"Erro durante validação do tabuleiro: {e}")
        return False

# --- Gerenciamento de Salas (Atualizado) ---

class GameRoom:
    """ Representa um único jogo (sala) """
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.host: Optional[WebSocket] = None
        self.guest: Optional[WebSocket] = None
        # Armazena dados mais complexos
        self.host_data: Dict = {}
        self.guest_data: Dict = {}
        # Armazena o placar da sala
        self.score: Dict[str, int] = {"host": 0, "guest": 0}
        logger.info(f"Sala {room_id} criada.")

    def is_full(self) -> bool:
        return self.host is not None and self.guest is not None

    def get_opponent(self, player: WebSocket) -> Optional[WebSocket]:
        if player == self.host: return self.guest
        if player == self.guest: return self.host
        return None

    def get_player_data(self, player: WebSocket) -> Optional[Dict]:
        if player == self.host: return self.host_data
        if player == self.guest: return self.guest_data
        return None

    def get_opponent_data(self, player: WebSocket) -> Optional[Dict]:
        if player == self.host: return self.guest_data
        if player == self.guest: return self.host_data
        return None

    def get_score(self, player: WebSocket) -> Dict[str, int]:
        """ Retorna o placar da perspectiva do jogador """
        if player == self.host:
            return {"you": self.score["host"], "opponent": self.score["guest"]}
        if player == self.guest:
            return {"you": self.score["guest"], "opponent": self.score["host"]}
        return {"you": 0, "opponent": 0}

    async def add_player(self, websocket: WebSocket, username: str) -> bool:
        """ Adiciona um jogador com seu nome de usuário """
        
        # Sanitiza o nome de usuário (evita nomes muito longos ou HTML)
        username = username.strip()[:15]
        
        if self.host is None:
            self.host = websocket
            self.host_data = {"username": username, "wants_rematch": False}
            await websocket.send_json({"type": "waiting_for_opponent"})
            logger.info(f"Jogador '{username}' ({getattr(websocket.client, 'port', 'unknown')}) é HOST da sala {self.room_id}")
            return True
        elif self.guest is None:
            self.guest = websocket
            self.guest_data = {"username": username, "wants_rematch": False}
            
            # Notifica ambos que o jogo começou, enviando nomes e placar
            await self.host.send_json({
                "type": "game_start", 
                "opponent_name": self.guest_data["username"],
                "my_name": self.host_data["username"],
                "score": self.get_score(self.host)
            })
            await self.guest.send_json({
                "type": "game_start", 
                "opponent_name": self.host_data["username"],
                "my_name": self.guest_data["username"],
                "score": self.get_score(self.guest)
            })
            logger.info(f"Jogador '{username}' ({getattr(websocket.client, 'port', 'unknown')}) é GUEST da sala {self.room_id}. Jogo começando.")
            return True
        else:
            await websocket.send_json({"type": "room_full"})
            return False

    async def remove_player(self, websocket: WebSocket):
        """ Remove um jogador e notifica o oponente """
        opponent = self.get_opponent(websocket)
        
        if websocket == self.host:
            self.host = None
            self.host_data = {}
        elif websocket == self.guest:
            self.guest = None
            self.guest_data = {}

        logger.info(f"Jogador {getattr(websocket.client, 'port', 'unknown')} saiu da sala {self.room_id}")

        # Notifica o oponente se ainda conectado
        try:
            if opponent and getattr(opponent, "client_state", None) and opponent.client_state.name == 'CONNECTED':
                await opponent.send_json({"type": "opponent_left"})
        except Exception:
            # Se enviar falhar, ignora (opponent desconectado)
            pass
            
    def reset_game_state(self):
        """ Limpa os tabuleiros e estados de revanche para um novo jogo """
        self.host_data.pop('board', None)
        self.guest_data.pop('board', None)
        self.host_data['wants_rematch'] = False
        self.guest_data['wants_rematch'] = False


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}

    def get_or_create_room(self, room_id: str) -> GameRoom:
        room_id = room_id.upper()
        if room_id not in self.rooms:
            self.rooms[room_id] = GameRoom(room_id)
        return self.rooms[room_id]

    def remove_room_if_empty(self, room_id: str):
        room_id = room_id.upper()
        if room_id in self.rooms:
            room = self.rooms[room_id]
            if room.host is None and room.guest is None:
                del self.rooms[room_id]
                logger.info(f"Sala vazia {room_id} removida.")

# --- Configuração do App ---
app = FastAPI()
manager = RoomManager()


# --- Endpoint do WebSocket (Atualizado para aceitar ambos 'setup_board' e 'board_setup') ---

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str = Path(..., min_length=4, max_length=4),
    # Recebe o nome de usuário pela URL
    username: str = Query(default="Jogador", min_length=1, max_length=15)
):
    
    await websocket.accept()
    
    room_id = room_id.upper()
    room = manager.get_or_create_room(room_id)

    if not await room.add_player(websocket, username):
        logger.warning(f"Jogador '{username}' tentou entrar na sala CHEIA {room_id}")
        await websocket.close(reason="Sala cheia ou nome inválido")
        return

    try:
        while True:
            data = await websocket.receive_json()
            
            opponent = room.get_opponent(websocket)
            my_data = room.get_player_data(websocket)
            opponent_data = room.get_opponent_data(websocket)
            
            # Garante que os jogadores ainda estão lá
            if not (opponent and my_data and opponent_data):
                logger.warning("Ação recebida, mas oponente/dados não encontrados. Ignorando.")
                continue

            # 1. Mensagem: "setup_board" OR "board_setup"
            # Aceitamos ambos os nomes para compatibilidade com diferentes clientes
            if data['type'] in ('setup_board', 'board_setup'):
                board_data = data.get('board')
                if not validate_board(board_data):
                    logger.warning(f"Jogador '{my_data.get('username','?')}' enviou tabuleiro INVÁLIDO.")
                    await websocket.send_json({"type": "error", "message": "Tabuleiro inválido."})
                    continue
                
                logger.info(f"Jogador '{my_data.get('username','?')}' enviou tabuleiro VÁLIDO.")
                my_data['board'] = board_data
                
                if 'board' in opponent_data:
                    logger.info(f"Ambos os jogadores na sala {room_id} estão prontos.")
                    my_data['turn'] = True
                    opponent_data['turn'] = False
                    await websocket.send_json({"type": "start_play", "turn": "you"})
                    await opponent.send_json({"type": "start_play", "turn": "opponent"})
                else:
                    await websocket.send_json({"type": "wait_for_setup"})
            
            # 2. Mensagem: "fire_shot"
            elif data['type'] == 'fire_shot':
                if not my_data.get('turn'):
                    await websocket.send_json({"type": "error", "message": "Não é sua vez."})
                    continue
                
                opponent_board = opponent_data.get('board')
                if not opponent_board: # Oponente ainda não configurou o tabuleiro
                    await websocket.send_json({"type": "error", "message": "O oponente não está pronto."})
                    continue
                
                pos = data.get('pos')
                if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
                    await websocket.send_json({"type": "error", "message": "Posição inválida."})
                    continue

                x, y = pos[0], pos[1]
                
                if not (isinstance(x, int) and isinstance(y, int) and 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
                    await websocket.send_json({"type": "error", "message": "Coordenada inválida."})
                    continue

                cell_value = opponent_board[y][x]
                result = ""

                if cell_value == 1:
                    opponent_board[y][x] = 2; result = "hit"
                elif cell_value == 0:
                    opponent_board[y][x] = -1; result = "miss"
                elif cell_value in (2, -1):
                    await websocket.send_json({"type": "error", "message": "Você já atirou aí."})
                    continue
                
                is_game_over = not any(1 in row for row in opponent_board)
                
                if is_game_over:
                    # Atualiza o placar
                    if websocket == room.host: room.score["host"] += 1
                    else: room.score["guest"] += 1
                    
                    logger.info(f"Jogo encerrado na sala {room_id}. Vencedor: {my_data.get('username','?')}")
                    
                    # Envia o resultado E o novo placar
                    await websocket.send_json({"type": "game_over", "result": "you_win", "score": room.get_score(websocket)})
                    await opponent.send_json({"type": "game_over", "result": "you_lose", "score": room.get_score(opponent)})
                else:
                    my_data['turn'] = False
                    opponent_data['turn'] = True
                    # Envia resultado ao atirador e notifica o oponente que recebeu o tiro
                    await websocket.send_json({"type": "shot_result", "pos": pos, "result": result, "turn": "opponent", "score": room.get_score(websocket)})
                    await opponent.send_json({"type": "shot_received", "pos": pos, "result": result, "turn": "you", "score": room.get_score(opponent)})

            # 3. Mensagem: "request_rematch"
            elif data['type'] == 'request_rematch':
                my_data['wants_rematch'] = True
                
                if opponent_data.get('wants_rematch'):
                    # Ambos querem revanche! Reinicia o jogo.
                    logger.info(f"Revanche aceita na sala {room_id}!")
                    room.reset_game_state()
                    
                    # Envia um novo 'game_start' para ambos
                    await room.host.send_json({
                        "type": "game_start", 
                        "opponent_name": room.guest_data["username"],
                        "my_name": room.host_data["username"],
                        "score": room.get_score(room.host)
                    })
                    await room.guest.send_json({
                        "type": "game_start", 
                        "opponent_name": room.host_data["username"],
                        "my_name": room.guest_data["username"],
                        "score": room.get_score(room.guest)
                    })
                else:
                    # Apenas este jogador quer (por enquanto)
                    logger.info(f"Jogador '{my_data.get('username','?')}' pediu revanche.")
                    await websocket.send_json({"type": "rematch_pending"})
                    await opponent.send_json({"type": "rematch_requested"})


    except WebSocketDisconnect:
        logger.info(f"WebSocketDisconnect: Jogador {getattr(websocket.client, 'port', 'unknown')} desconectou da sala {room_id}")
    except Exception as e:
        logger.error(f"Erro inesperado no websocket {getattr(websocket.client, 'port', 'unknown')}: {e}")
    finally:
        await room.remove_player(websocket)
        manager.remove_room_if_empty(room_id)


@app.get("/")
async def get():
    with open("client.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())
