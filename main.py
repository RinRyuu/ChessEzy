import socket
import qrcode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import chess    # NEW: The backend chess engine
import random   
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

rooms = {}
current_room_id = 1

# --- NEW: Simple Python AI Bot ---
def get_ai_move(board: chess.Board):
    legal_moves = list(board.legal_moves)
    
    # 1. Look for a winning checkmate move
    for move in legal_moves:
        board.push(move)
        if board.is_checkmate():
            board.pop()
            return move
        board.pop()

    # 2. Look for captures (greedy bot)
    captures = [move for move in legal_moves if board.is_capture(move)]
    if captures:
        return random.choice(captures)
    
    # 3. Otherwise, play a random legal move
    return random.choice(legal_moves)


@app.get("/")
async def get():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# NEW: Added 'mode' parameter to route traffic
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, name: str = "Anonymous", mode: str = "multi"):
    global current_room_id
    await websocket.accept()

    # ==========================================
    # MODE 1: PLAY VS AI (BOT)
    # ==========================================
    if mode == "ai":
        # Initialize isolated board for this player
        ai_board = chess.Board()
        room_name = f"AI_{id(websocket)}"
        
        # Player is always White vs AI
        await websocket.send_json({"type": "init", "color": "w", "room": "AI-Lobby", "name": name})
        await websocket.send_json({"type": "start", "opponent_name": "Python Bot 🤖"})
        
        try:
            while True:
                # Wait for player move
                data = await websocket.receive_json()
                source = data["source"]
                target = data["target"]
                
                # Apply player move to backend board (e.g., "e2e4")
                player_move = chess.Move.from_uci(f"{source}{target}")
                
                # Handle pawn promotion to queen format
                if not player_move in ai_board.legal_moves:
                    player_move = chess.Move.from_uci(f"{source}{target}q")
                
                if player_move in ai_board.legal_moves:
                    ai_board.push(player_move)
                    
                    # If game is over after player move, wait and do nothing
                    if ai_board.is_game_over():
                        continue

                    # Simulate bot thinking time
                    await asyncio.sleep(0.5) 
                    
                    # Generate and apply AI Move
                    ai_move = get_ai_move(ai_board)
                    ai_board.push(ai_move)
                    
                    # Send AI move back to frontend
                    move_str = ai_move.uci() # e.g., "e7e5"
                    await websocket.send_json({
                        "type": "move", 
                        "source": move_str[:2], 
                        "target": move_str[2:]
                    })
                    
        except WebSocketDisconnect:
            pass # AI doesn't care if you leave
        return # Exit the function, skip the multiplayer logic


    # ==========================================
    # MODE 2: PLAY VS HUMAN (LAN) - Your existing logic
    # ==========================================
    if current_room_id not in rooms:
        rooms[current_room_id] = []
    
    room_id = current_room_id
    color = 'w' if len(rooms[room_id]) == 0 else 'b'
    
    player_data = {"ws": websocket, "name": name, "color": color}
    rooms[room_id].append(player_data)

    await websocket.send_json({"type": "init", "color": color, "room": room_id, "name": name})

    if len(rooms[room_id]) == 2:
        p1, p2 = rooms[room_id][0], rooms[room_id][1]
        current_room_id += 1
        
        await p1["ws"].send_json({"type": "start", "opponent_name": p2["name"]})
        await p2["ws"].send_json({"type": "start", "opponent_name": p1["name"]})

    try:
        while True:
            data = await websocket.receive_json()
            for p in rooms[room_id]:
                if p["ws"] != websocket:
                    await p["ws"].send_json(data)
                    
    except WebSocketDisconnect:
        rooms[room_id] = [p for p in rooms[room_id] if p["ws"] != websocket]
        for p in rooms[room_id]:
            await p["ws"].send_json({"type": "disconnect", "message": "Opponent disconnected."})


if __name__ == "__main__":
    ip = get_lan_ip()
    port = 8000
    url = f"http://{ip}:{port}"
    
    print(f"Starting server at {url}")
    qr = qrcode.make(url)
    qr.show() 

    uvicorn.run(app, host="0.0.0.0", port=port)