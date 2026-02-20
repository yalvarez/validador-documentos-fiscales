import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'webhook.sqlite3')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS webhook_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

app = FastAPI()

app.mount('/static', StaticFiles(directory=os.path.join(os.path.dirname(__file__), 'static')), name='static')
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

@app.post('/webhook')
async def receive_webhook(request: Request):
    data = await request.body()
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT INTO webhook_data (payload) VALUES (?)', (data.decode('utf-8'),))
    conn.commit()
    conn.close()
    return {'status': 'ok'}

@app.get('/', response_class=HTMLResponse)
def show_webhook_data(request: Request):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('SELECT id, payload, created_at FROM webhook_data ORDER BY created_at DESC').fetchall()
    conn.close()
    return templates.TemplateResponse('table.html', {'request': request, 'rows': rows})
