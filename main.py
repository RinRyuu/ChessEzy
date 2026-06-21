import socket
import qrcode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

app = FastAPI()

# Mount the static directory so the frontend can access CSS and JS files
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

# State Management: Now stores dictionaries with names and websockets
rooms = {}
current_room_id = 1

@app.get("/")
async def get():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r") as f:
        return HTMLResponse(f.read())

# Notice we added 'name' as a parameter to grab it from the URL
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, name: str = "Anonymous"):
    global current_room_id
    await websocket.accept()

    if current_room_id not in rooms:
        rooms[current_room_id] = []
    
    room_id = current_room_id
    color = 'w' if len(rooms[room_id]) == 0 else 'b'
    
    # Store the player's info
    player_data = {"ws": websocket, "name": name, "color": color}
    rooms[room_id].append(player_data)

    await websocket.send_json({"type": "init", "color": color, "room": room_id, "name": name})

    # If room is full, start the game and exchange names
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
        # Remove the disconnected player and notify the other
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