// 1. Prompt for name immediately
let playerName = prompt("Welcome to ChessEzy! Enter your name:") || "Anonymous";

let board = null;
let game = new Chess();
let myColor = 'w';
let opponentName = "Waiting...";
let gameStarted = false;

// 2. Connect to WebSocket, passing the name in the URL
let ws_url = `ws://${window.location.host}/ws?name=${encodeURIComponent(playerName)}`;
let socket = new WebSocket(ws_url);

// --- Highlighting Logic ---
const whiteSquareGrey = '#a9a9a9';
const blackSquareGrey = '#696969';

function removeGreySquares() {
    $('#board .square-55d63').css('background', '');
}

function greySquare(square) {
    let $square = $('#board .square-' + square);
    let background = $square.hasClass('black-3c85d') ? blackSquareGrey : whiteSquareGrey;
    $square.css('background', background);
}

// --- WebSocket Handling ---
socket.onmessage = function(event) {
    let data = JSON.parse(event.data);

    if (data.type === 'init') {
        myColor = data.color;
        board.orientation(myColor === 'w' ? 'white' : 'black');
        document.getElementById('status-msg').innerText = `Room ${data.room}: Waiting for opponent...`;
        
        // Update local player card
        let myCard = myColor === 'w' ? '#player-w' : '#player-b';
        $(myCard).text(`${playerName} (${myColor === 'w' ? 'White' : 'Black'})`);
    } 
    else if (data.type === 'start') {
        gameStarted = true;
        opponentName = data.opponent_name;
        
        // Update opponent player card
        let oppCard = myColor === 'w' ? '#player-b' : '#player-w';
        $(oppCard).text(`${opponentName} (${myColor === 'w' ? 'Black' : 'White'})`);
        
        document.getElementById('status-msg').innerText = "Game On!";
        updateTurnUI();
    } 
    else if (data.type === 'move') {
        game.move({ from: data.source, to: data.target, promotion: 'q' });
        board.position(game.fen());
        updateTurnUI();
    }
    else if (data.type === 'disconnect') {
        document.getElementById('status-msg').innerText = data.message;
        document.getElementById('status-msg').classList.add('win-text');
        gameStarted = false;
        $('.player-card').removeClass('active-turn');
    }
};

// --- Chessboard Functions ---
function onDragStart(source, piece, position, orientation) {
    if (!gameStarted || game.game_over()) return false;
    if ((myColor === 'w' && piece.search(/^b/) !== -1) ||
        (myColor === 'b' && piece.search(/^w/) !== -1)) return false;
    if ((game.turn() === 'w' && myColor === 'b') || 
        (game.turn() === 'b' && myColor === 'w')) return false;

    // Highlight possible moves
    let moves = game.moves({ square: source, verbose: true });
    if (moves.length === 0) return;
    for (let i = 0; i < moves.length; i++) {
        greySquare(moves[i].to);
    }
}

function onDrop(source, target) {
    removeGreySquares(); // Clear highlights when piece is dropped

    let move = game.move({ from: source, to: target, promotion: 'q' });
    if (move === null) return 'snapback';

    socket.send(JSON.stringify({ type: 'move', source: source, target: target }));
    updateTurnUI();
}

function onSnapEnd() {
    board.position(game.fen());
}

// Ensure highlights are removed if a piece is picked up and dropped back in place
function onSnapbackEnd() {
    removeGreySquares(); 
}

// --- Dynamic UI Updater ---
function updateTurnUI() {
    let statusEl = document.getElementById('status-msg');
    let pWhite = document.getElementById('player-w');
    let pBlack = document.getElementById('player-b');

    // Reset UI
    pWhite.classList.remove('active-turn');
    pBlack.classList.remove('active-turn');
    statusEl.classList.remove('win-text');

    if (game.in_checkmate()) { 
        let winner = game.turn() === 'w' ? 'Black' : 'White';
        let winnerName = (winner.toLowerCase() === myColor) ? playerName : opponentName;
        statusEl.innerText = `CHECKMATE! ${winnerName} Wins!`;
        statusEl.classList.add('win-text');
    } 
    else if (game.in_draw()) { 
        statusEl.innerText = 'Game Over - Draw!';
    } 
    else { 
        // Highlight whose turn it is
        if (game.turn() === 'w') {
            pWhite.classList.add('active-turn');
            statusEl.innerText = "White to move";
        } else {
            pBlack.classList.add('active-turn');
            statusEl.innerText = "Black to move";
        }
        
        if (game.in_check()) { 
            statusEl.innerText += ' (IN CHECK)';
            statusEl.style.color = '#e74c3c'; // Make text red if in check
        } else {
            statusEl.style.color = '#f1c40f'; // Default yellow
        }
    }
}

let config = {
    pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png',
    draggable: true,
    position: 'start',
    onDragStart: onDragStart,
    onDrop: onDrop,
    onSnapEnd: onSnapEnd,
    onSnapbackEnd: onSnapbackEnd // Hook to clear highlights if move cancelled
};
board = Chessboard('board', config);

$(window).resize(board.resize);