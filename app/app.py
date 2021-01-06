#!/usr/bin/env python3

import json

rooms = {}

async def send(ws, obj):
    if not ws.closed:
        print('>', obj)
        await ws.send_str(json.dumps(obj))

async def kick(ws):
    await send(ws, {'type': 'kick' })
    await ws.close()

class Room:
    def __init__(self, name, ws):
        self.name = name
        self.clients = set()
        self.presenter = ws
        self.is_opened = False
        self.json = '{}'
        self.page = 0

    async def notify_clients(self, msg):
        clients = self.clients.copy()
        for w in clients:
            await send(w, msg)

    async def change_page(self, page):
        if page != self.page:
            self.page = page
            await self.notify_clients({ 'type': 'page_changed', 'page': page })

    async def join(self, w):
        self.clients.add(w)
        await send(w, { 'type': 'room_opened', 'json': self.json, 'page': self.page })
        await send(self.presenter, { 'type': 'nb_connected', 'nb': len(self.clients) })

    async def quit(self, w):
        self.clients.discard(w)
        await send(self.presenter, { 'type': 'nb_connected', 'nb': len(self.clients) })

    async def open(self, j):
        self.is_opened = True
        self.json = j
        await self.notify_clients({ 'type': 'room_opened', 'json': self.json, 'page': self.page })

    async def close(self):
        clients = self.clients.copy()
        for w in clients:
            await send(w, { 'type': 'room_closed' })
            await w.close()

async def presenter_msg(ws, json):
    room = ws.userData['room']
    if json['type'] == 'connection_closed':
        await room.close()
        rooms.pop(room.name, None)

    elif json['type'] == 'open_room':
        if not 'json' in json: kick(ws)
        await room.open(json['json'])

    elif json['type'] == 'change_page':
        if not 'page' in json: kick(ws)
        await room.change_page(json['page'])

    else:
        kick(ws)

async def client_msg(ws, json):
    room = ws.userData['room']
    if json['type'] == 'connection_closed':
        await room.quit(ws)

    else:
        kick(ws)

async def websocket_json_msg(ws, json):
    print('<', json)
    if not 'type' in json: await kick(ws)
    if 'role' in ws.userData: await ws.userData['role'](ws, json)

    if json['type'] == 'connect':
        if not 'room' in json: kick(ws)
        r = json['room']
        if not r in rooms or not rooms[r].is_opened:
            await send(ws, { 'type': 'room_currently_closed' })
            await ws.close()
        else:
            await rooms[r].join(ws)
            ws.userData['role'] = client_msg
            ws.userData['room'] = rooms[r]

    elif json['type'] == 'init_room':
        if not 'room' in json: kick(ws)
        r = json['room']
        if r in rooms:
            await send(ws, { 'type': 'room_already_opened' })
            await ws.close()
        else:
            rooms[r] = Room(r, ws)
            ws.userData['role'] = presenter_msg
            ws.userData['room'] = rooms[r]

