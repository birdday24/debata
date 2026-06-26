# server.py
import eventlet
eventlet.monkey_patch() # Nutné pro produkční server

import threading
import requests
from flask import Flask
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__, static_url_path='', static_folder='public')
app.config['SECRET_KEY'] = 'tajny-klic-areny'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

OPENROUTER_API_KEY = "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"
MODEL_NAME = "openai/gpt-oss-20b:free"

JUDGE_PROMPT = """Jsi nekompromisní, drsný a sarkastický soudce v debatní aréně. 
Dva lidé se právě hádají o nějakém tématu. Tvá role:
1. Přečti si jejich argumenty.
2. Rozhodni, kdo má lepší argumenty (logika, fakta, přesvědčivost).
3. Vítěze lehce pochval (ale udrž si arogantní tón).
4. Poraženého absolutně znič, zroastuj jeho nelogické nesmysly a udělej si z něj srandu.
Odpovídej stručně, úderně a jako bys byl ten nejchytřejší člověk v místnosti."""

# Zde si server pamatuje historii zpráv pro každou místnost
room_histories = {}

@app.route('/')
def index():
    return app.send_static_file('index.html')

@socketio.on('join')
def on_join(data):
    username = data['user']
    room = data['room']
    join_room(room)
    
    if room not limitation in room_histories:
        room_histories[room] = []
        
    emit('receive_message', {'user': '🏛️ ARÉNA', 'text': f'{username} vstoupil do ringu.', 'type': 'system'}, to=room)

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    user = data['user']
    text = data['text']
    
    # Uložíme do historie místnosti
    room_histories[room].append(f"{user}: {text}")
    
    # Pošleme zprávu všem v místnosti
    emit('receive_message', {'user': user, 'text': text, 'type': 'user'}, to=room)

def call_ai_judge(room):
    history = "\n".join(room_histories.get(room, []))
    if not history: return

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": f"Zde je přepis debaty. Rozhodni:\n\n{history}"}
        ],
        "temperature": 0.9
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        reply = response.json()['choices'][0]['message']['content']
        socketio.emit('receive_message', {'user': '🤖 AI SOUDCE', 'text': reply, 'type': 'judge'}, to=room)
        room_histories[room] = [] # Vymaže historii po rozsudku
    except Exception as e:
        print(f"Chyba soudce: {e}")

@socketio.on('call_judge')
def handle_judge(data):
    room = data['room']
    emit('receive_message', {'user': '🏛️ ARÉNA', 'text': 'Soudce analyzuje argumenty...', 'type': 'system'}, to=room)
    threading.Thread(target=call_ai_judge, args=(room,)).start()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=3000)