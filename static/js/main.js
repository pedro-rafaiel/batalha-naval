// --- CAMADA DE MIDDLEWARE (STUB/RPC) ---
class GameServerProxy {
    constructor(ws) {
        this.ws = ws;
    }

    call(type, payload = {}) {
        if (this.ws.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({ type, ...payload });
            this.ws.send(message);
        } else {
            console.warn("WebSocket não está aberto. Estado:", this.ws.readyState);
        }
    }
}

// --- VARIÁVEIS DE ESTADO ---
const BOARD_SIZE = 5;
const SHIP_COUNT = 5;
let server = null;
let meuTabuleiro = Array(BOARD_SIZE).fill(0).map(() => Array(BOARD_SIZE).fill(0));
let shipsPlaced = 0;
let isMyTurn = false;

// --- ELEMENTOS UI ---
const statusEl = document.getElementById("status");
const infoEl = document.getElementById("game-room-info");
const joinButton = document.getElementById("joinButton");
const createButton = document.getElementById("createButton");
const prepareButton = document.getElementById("prepareButton");
const rematchButton = document.getElementById("rematchButton");

// --- LÓGICA DE CONEXÃO ---
function connect() {
    const roomIdInput = document.getElementById("roomInput");
    const usernameInput = document.getElementById("usernameInput");
    
    const roomId = roomIdInput.value.toUpperCase();
    const username = usernameInput.value.trim();
    
    if (!username || roomId.length !== 4) {
        return alert("Por favor, insira um nome e um código de sala de 4 dígitos.");
    }

    statusEl.innerText = "Conectando ao servidor...";

    // Identifica se está rodando localmente ou na web
    const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    
    // Seu host do Render conforme imagem image_259505.png
    const backendHost = isLocal ? "127.0.0.1:8000" : "batalha-naval-2scs.onrender.com";
    
    // Força WSS (seguro) se a página estiver em HTTPS (Vercel)
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${protocol}://${backendHost}/ws/${roomId}?username=${username}`;
    
    console.log("Tentando conectar em:", wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("Conectado com sucesso!");
        server = new GameServerProxy(ws);
        document.getElementById("lobby-container").style.display = 'none';
        document.getElementById("game-container").style.display = 'block';
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
    };

    ws.onclose = (event) => {
        console.log("WebSocket fechado:", event);
        statusEl.innerText = "Conexão perdida. O servidor pode estar iniciando...";
        // Tenta reconectar após 5 segundos se o servidor estiver "acordando"
        if (!isLocal) {
            setTimeout(connect, 5000);
        }
    };

    ws.onerror = (error) => {
        console.error("Erro no WebSocket:", error);
        statusEl.innerText = "Erro ao conectar. O servidor do Render está acordando, aguarde...";
    };
}

// --- DESPACHANTE DE MENSAGENS ---
function handleServerMessage(msg) {
    const roomId = document.getElementById("roomInput").value.toUpperCase();

    switch(msg.type) {
        case 'waiting_for_opponent':
            infoEl.innerText = `SALA: ${roomId}`;
            statusEl.innerText = "Aguardando um oponente entrar...";
            break;

        case 'game_start':
            shipsPlaced = 0;
            meuTabuleiro = Array(BOARD_SIZE).fill(0).map(() => Array(BOARD_SIZE).fill(0));
            isMyTurn = false;
            infoEl.innerText = `SALA: ${roomId} | Oponente: ${msg.opponent_name}`;
            statusEl.innerText = "Posicione seus 5 navios";
            setupGrids();
            prepareButton.style.display = 'block';
            rematchButton.style.display = 'none';
            document.getElementById("opponent-board").classList.remove("turn-disabled");
            break;

        case 'start_play':
            setTurn(msg.turn === 'you');
            break;

        case 'shot_result':
            updateGridDisplay("opponent-board", msg.pos, msg.result);
            if (msg.turn) setTurn(msg.turn === 'you');
            break;

        case 'shot_received':
            updateGridDisplay("my-board", msg.pos, msg.result);
            if (msg.turn) setTurn(msg.turn === 'you');
            break;

        case 'game_over':
            const isWin = msg.result === 'you_win';
            statusEl.innerText = isWin ? "VITÓRIA!" : "DERROTA!";
            document.getElementById("opponent-board").classList.add("turn-disabled");
            rematchButton.style.display = 'block';
            break;

        case 'error':
            alert(msg.message);
            break;
    }
}

// --- FUNÇÕES DE GRID ---
function setupGrids() {
    createGrid("my-board", true);
    createGrid("opponent-board", true);
}

function createGrid(id, clickable) {
    const table = document.querySelector(`#${id} .grid`);
    if (!table) return;
    table.innerHTML = "";
    for (let y = 0; y < BOARD_SIZE; y++) {
        let tr = document.createElement("tr");
        for (let x = 0; x < BOARD_SIZE; x++) {
            let td = document.createElement("td");
            td.dataset.x = x; 
            td.dataset.y = y;
            if (clickable) td.onclick = () => onCellClick(id, x, y, td);
            tr.appendChild(td);
        }
        table.appendChild(tr);
    }
}

function onCellClick(boardId, x, y, cell) {
    if (boardId === 'my-board' && shipsPlaced < SHIP_COUNT) {
        if (meuTabuleiro[y][x] === 0) {
            meuTabuleiro[y][x] = 1;
            shipsPlaced++;
            cell.classList.add("cell-ship");
        }
    } else if (boardId === 'opponent-board' && isMyTurn) {
        if (cell.classList.contains("cell-hit") || cell.classList.contains("cell-miss")) return;
        server.call('fire_shot', { pos: [x, y] });
        setTurn(false);
    }
}

function updateGridDisplay(boardId, pos, result) {
    const cell = document.querySelector(`#${boardId} td[data-x="${pos[0]}"][data-y="${pos[1]}"]`);
    if (cell) cell.classList.add(result === 'hit' ? "cell-hit" : "cell-miss");
}

function setTurn(myTurn) {
    isMyTurn = myTurn;
    statusEl.innerText = myTurn ? "Sua vez!" : "Vez do oponente...";
    document.getElementById("opponent-board").classList.toggle("turn-disabled", !myTurn);
}

// --- EVENTOS ---
joinButton.onclick = connect;
createButton.onclick = () => {
    const code = Math.random().toString(36).substring(2, 6).toUpperCase();
    document.getElementById("roomInput").value = code;
    connect();
};
prepareButton.onclick = () => {
    if (shipsPlaced === SHIP_COUNT) {
        server.call('board_setup', { board: meuTabuleiro });
        prepareButton.style.display = 'none';
    }
};
rematchButton.onclick = () => {
    server.call('request_rematch');
    rematchButton.style.display = 'none';
};