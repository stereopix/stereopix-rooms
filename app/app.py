#!/usr/bin/env python3

import json

class Room:
    def __init__(self, name, ws):
        self.name = name
        self.clients = set()
        self.presenter = ws
        self.is_opened = False
        self.json = '{}'

    async def notify_clients(self, msg):
        clients = self.clients.copy()
        for w in clients:
            await send(w, msg)

    async def join(self, w):
        self.clients.add(w)
        await send(w, { 'type': 'room_opened', 'json': self.json })

    async def quit(self, w):
        self.clients.discard(w)

    async def open(self, j):
        self.is_opened = True
        self.json = j

    async def close(self):
        clients = self.clients.copy()
        for w in clients:
            await send(w, { 'type': 'room_closed' })
            await w.close()

rooms = {}

async def send(ws, obj):
    if not ws.closed:
        await ws.send_str(json.dumps(obj))

async def kick(ws): 
    await ws.send_str(json.dumps({'type': 'kick' }))
    await ws.close()

async def websocket_json_msg(ws, json): 
    print(json)
    if not 'type' in json: await kick(ws)

    if json['type'] == 'connection_closed':
        if 'presents' in ws.userData:
            room = ws.userData['presents']
            await room.close()
            rooms.pop(room.name, None)
        elif 'room' in ws.userData:
            room = ws.userData['room']
            await room.quit(ws)

    if json['type'] == 'connect':
        if not 'room' in json: kick(ws)
        r = json['room']
        if not r in rooms or not rooms[r].is_opened:
            await send(ws, { 'type': 'room_currently_closed' })
            await ws.close()
        else:
            await rooms[r].join(ws)
            ws.userData['room'] = rooms[r]

    if json['type'] == 'init_room':
        if not 'room' in json: kick(ws)
        r = json['room']
        if r in rooms:
            await send(ws, { 'type': 'room_already_opened' })
            await ws.close()
        else:
            rooms[r] = Room(r, ws)
            ws.userData['presents'] = rooms[r]

    if json['type'] == 'open_room':
        if not 'json' in json: kick(ws)
        await ws.userData['presents'].open(json['json'])
