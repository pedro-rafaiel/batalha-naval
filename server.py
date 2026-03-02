import asyncio
import json
import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Path, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Dict, Optional

# Configuracao de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOARD_SIZE = 5
SHIP_COUNT = 5
DB_FILE = "persistent_scores.json"

# --- 1. CAMADA DE PERSISTENCIA ---
class ScoreDatabase:
    def __init__(self, filename: str):
        self.filename = filename
        if not os.path.exists(self.filename):
            self._write({})

    def _read(self) -> Dict[str, int]:
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, data: Dict[str, int]):
        with open(self.filename, 'w') as f:
            json.dump(data, f, indent=4)

    def increment_win(self, username: str):
        scores = self._read()
        scores[username] = scores.get(username, 0) + 1
        self._write(scores)

db = ScoreDatabase(DB_FILE)

# --- 2. LOGICA DE NEGOCIO ---
def validate_board(board: list) -> bool:
    try:
        if not (isinstance(board, list) and len(board) == BOARD_SIZE):
            return False
        total_ships = sum(row.count(1) for row in board if isinstance(row, list))
        return total_ships == SHIP_COUNT
    except Exception:
        return False

class GameRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.host: Optional[WebSocket] = None
        self.guest: Optional[WebSocket] = None
        self.host_data = {"username": "", "wants_rematch": False, "turn": False}
        self.guest_data = {"username": "", "wants_rematch": False, "turn": False}

    def get_opponent(self, player: WebSocket):
        return self.guest if player == self.host else self.host

    def get_player_data(self, player: WebSocket):
        return self.host_data if player == self.host else self.guest_data

    def get_opponent_data(self, player: WebSocket):
        return self.guest_data if player == self.host else self.host_data

    def reset_game_state(self):
        self.host_data = {"username": self.host_data["username"], "wants_rematch": False, "turn": False}
        self.guest_data = {"username": self.guest_data["username"], "wants_rematch": False, "turn": False}

# --- 3. CAMADA DE COMUNICACAO ---
class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}

    def get_or_create(self, room_id: str) -> GameRoom:
        rid = room_id.upper()
        if rid not in self.rooms:
            self.rooms[rid] = GameRoom(rid)
        return self.rooms[rid]

manager = RoomManager()
app = FastAPI()

base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")

@app.get("/")
async def get_index():
    return FileResponse(os.path.join(static_dir, "client.html"))

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str = Path(...), username: str = Query(...)):
    await websocket.accept()
    room = manager.get_or_create(room_id)
    
    if not room.host:
        room.host = websocket
        room.host_data["username"] = username
        await websocket.send_json({"type": "waiting_for_opponent"})
    elif not room.guest:
        room.guest = websocket
        room.guest_data["username"] = username
        await room.host.send_json({"type": "game_start", "opponent_name": username})
        await room.guest.send_json({"type": "game_start", "opponent_name": room.host_data["username"]})
    else:
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()
            opp = room.get_opponent(websocket)
            my_data = room.get_player_data(websocket)
            opp_data = room.get_opponent_data(websocket)

            if not opp: continue

            if data['type'] == 'board_setup':
                if validate_board(data.get('board')):
                    my_data['board'] = data['board']
                    if 'board' in my_data and 'board' in opp_data:
                        room.host_data['turn'] = True
                        room.guest_data['turn'] = False
                        await room.host.send_json({"type": "start_play", "turn": "you"})
                        await room.guest.send_json({"type": "start_play", "turn": "opponent"})
                    else:
                        await websocket.send_json({"type": "wait_for_setup"})

            elif data['type'] == 'fire_shot':
                if not my_data.get('turn'): continue
                x, y = data['pos']
                opp_board = opp_data.get('board')

                if opp_board[y][x] in [-1, 2]:
                    await websocket.send_json({"type": "error", "message": "Já atirou aqui!"})
                    continue

                if opp_board[y][x] == 1:
                    opp_board[y][x] = 2
                    result = "hit"
                else:
                    opp_board[y][x] = -1
                    result = "miss"

                is_win = not any(1 in row for row in opp_board)
                if is_win:
                    db.increment_win(my_data["username"])
                    await websocket.send_json({"type": "game_over", "result": "you_win"})
                    await opp.send_json({"type": "game_over", "result": "you_lose"})
                else:
                    my_data['turn'] = False
                    opp_data['turn'] = True
                    await websocket.send_json({"type": "shot_result", "pos": [x,y], "result": result, "turn": "opponent"})
                    await opp.send_json({"type": "shot_received", "pos": [x,y], "result": result, "turn": "you"})

            elif data['type'] == 'request_rematch':
                my_data['wants_rematch'] = True
                if opp_data.get('wants_rematch'):
                    room.reset_game_state()
                    await room.host.send_json({"type": "game_start", "opponent_name": room.guest_data["username"]})
                    await room.guest.send_json({"type": "game_start", "opponent_name": room.host_data["username"]})
                else:
                    await opp.send_json({"type": "rematch_requested"})

    except WebSocketDisconnect:
        if opp: await opp.send_json({"type": "opponent_left"})
        if websocket == room.host: room.host = None
        else: room.guest = None

app.mount("/", StaticFiles(directory=static_dir), name="static")