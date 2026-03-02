// --- CAMADA DE MIDDLEWARE (STUB/RPC) ---
class GameServerProxy {
    constructor(ws) {
        this.ws = ws;
    }

    call(type, payload = {}) {
        const message = JSON.stringify({ type, ...payload });
        this.ws.send(message);
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

    const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    
    const backendHost = isLocal ? "127.0.0.1:8000" : "seu-backend-no-render.onrender.com";
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";

    const ws = new WebSocket(`${protocol}://${backendHost}/ws/${roomId}?username=${username}`);

    ws.onopen = () => {
        server = new GameServerProxy(ws);
        document.getElementById("lobby-container").style.display = 'none';
        document.getElementById("game-container").style.display = 'block';
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
    };

    ws.onerror = (error) => {
        console.error("Erro no WebSocket:", error);
        statusEl.innerText = "Erro de conexão com o servidor.";
    };
}

// --- DESPACHANTE DE MENSAGENS (RPC RECEIVER) ---
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
            statusEl.innerText = "Posicione seus 5 navios no seu tabuleiro";
            
            setupGrids();
            
            prepareButton.style.display = 'block';
            rematchButton.style.display = 'none';
            document.getElementById("opponent-board").classList.remove("turn-disabled");
            break;

        case 'wait_for_setup':
            statusEl.innerText = "Aguardando oponente posicionar os navios...";
            prepareButton.style.display = 'none';
            break;

        case 'start_play':
            setTurn(msg.turn === 'you');
            break;

        case 'shot_result':
            updateGridDisplay("opponent-board", msg.pos, msg.result);
            // Sincroniza o turno baseado na resposta do servidor
            if (msg.turn) setTurn(msg.turn === 'you');
            break;

        case 'shot_received':
            updateGridDisplay("my-board", msg.pos, msg.result);
            // Sincroniza o turno baseado na resposta do servidor
            if (msg.turn) setTurn(msg.turn === 'you');
            break;

        case 'rematch_requested':
            statusEl.innerText = "O oponente quer uma revanche!";
            break;

        case 'game_over':
            const isWin = msg.result === 'you_win';
            const imgPath = isWin ? 'img/win.svg' : 'img/lose.svg';
            
            statusEl.innerHTML = `
                <div style="text-align:center">
                    <img src="${imgPath}" style="width:80px; display:block; margin: 0 auto 10px">
                    <span style="color: ${isWin ? '#64ffda' : '#ff4d4d'}">
                        ${isWin ? "VITÓRIA GLORIOSA!" : "VOCÊ FOI AFUNDADO..."}
                    </span>
                </div>
            `;
            
            document.getElementById("opponent-board").classList.add("turn-disabled");
            rematchButton.style.display = 'block';
            break;

        case 'opponent_left':
            statusEl.innerText = "Oponente desconectou.";
            infoEl.innerText = "Partida encerrada.";
            rematchButton.style.display = 'none';
            break;
            
        case 'error':
            alert(msg.message);
            if (msg.message.includes("vez") || msg.message.includes("atirou")) {
                setTurn(true);
            }
            break;
    }
}

// --- FUNÇÕES DE INTERFACE ---
function setupGrids() {
    createGrid("my-board", true);
    createGrid("opponent-board", true);
}

function createGrid(id, clickable) {
    const table = document.querySelector(`#${id} .grid`);
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
    } 
    else if (boardId === 'opponent-board' && isMyTurn) {
        if (cell.classList.contains("cell-hit") || cell.classList.contains("cell-miss")) {
            return;
        }
        
        server.call('fire_shot', { pos: [x, y] });
        setTurn(false); 
    }
}

function updateGridDisplay(boardId, pos, result) {
    const [x, y] = pos;
    const cell = document.querySelector(`#${boardId} td[data-x="${x}"][data-y="${y}"]`);
    if (!cell) return;

    if (result === 'hit') {
        cell.classList.add("cell-hit");
    } else {
        cell.classList.add("cell-miss");
    }
}

function setTurn(myTurn) {
    isMyTurn = myTurn;
    statusEl.innerText = myTurn ? "Sua vez de atirar!" : "Aguarde a vez do oponente...";
    
    const oppBoard = document.getElementById("opponent-board");
    if (myTurn) {
        oppBoard.classList.remove("turn-disabled");
        document.body.classList.add("my-turn");
        document.body.classList.remove("opponent-turn");
    } else {
        oppBoard.classList.add("turn-disabled");
        document.body.classList.remove("my-turn");
        document.body.classList.add("opponent-turn");
    }
}

// --- EVENTOS DE CLIQUE ---
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
    } else {
        alert(`Posicione todos os ${SHIP_COUNT} navios primeiro!`);
    }
};

rematchButton.onclick = () => {
    server.call('request_rematch');
    rematchButton.style.display = 'none';
    statusEl.innerText = "Aguardando oponente aceitar revanche...";
};