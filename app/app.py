#!/usr/bin/env python3

import json

rooms = {}

async def send(ws, obj):
    if not ws.closed:
        print('>', obj)
        try:
            await ws.send_str(json.dumps(obj))
        except ConnectionResetError:
            print('> ERROR')

class Kick(BaseException):
    pass

class Room:
    def __init__(self, name, ws):
        self.name = name
        self.clients = set()
        self.presenter = ws
        self.is_opened = False
        self.allow_stealing = False
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

    async def steal(self, ws):
        self.allow_stealing = False
        await send(self.presenter, { 'type': 'room_stolen_kick' })
        self.presenter.userData.pop('room', None)
        self.presenter.userData.pop('role', None)
        await self.presenter.close()
        self.presenter = ws
        await send(self.presenter, { 'type': 'room_stolen', 'json': self.json, 'page': self.page })

    async def open(self, j):
        self.is_opened = True
        self.json = j
        await self.notify_clients({ 'type': 'room_opened', 'json': self.json, 'page': self.page })

    async def close(self):
        clients = self.clients.copy()
        for w in clients:
            await send(w, { 'type': 'room_closed' })
            w.userData.pop('room', None)
            w.userData.pop('role', None)
            await w.close()

def is_opened(r):
    return r in rooms and rooms[r].is_opened

async def presenter_msg(ws, json):
    room = ws.userData['room']
    if json['type'] == 'connection_closed':
        await room.close()
        rooms.pop(room.name, None)

    elif json['type'] == 'open_room':
        if not 'json' in json: raise Kick()
        await room.open(json['json'])

    elif json['type'] == 'allow_stealing':
        if not 'value' in json: raise Kick()
        room.allow_stealing = json['value']

    elif json['type'] == 'change_page':
        if not 'page' in json: raise Kick()
        await room.change_page(json['page'])

    else:
        raise Kick()

async def client_msg(ws, json):
    room = ws.userData['room']
    if json['type'] == 'connection_closed':
        await room.quit(ws)

    else:
        raise Kick()

async def websocket_json_msg(ws, json):
    print('<', json)
    if not 'type' in json: raise Kick()
    if 'role' in ws.userData:
        await ws.userData['role'](ws, json)

    elif json['type'] == 'hello':
        if not 'action' in json: raise Kick()
        if not 'room' in json: raise Kick()
        r = json['room']
        if json['action'] == 'attend':
            if not is_opened(r):
                await send(ws, { 'type': 'room_currently_closed' })
                await ws.close()
            else:
                await rooms[r].join(ws)
                ws.userData['role'] = client_msg
                ws.userData['room'] = rooms[r]
        elif json['action'] == 'present':
            if r in rooms:
                if rooms[r].allow_stealing:
                    ws.userData['role'] = presenter_msg
                    ws.userData['room'] = rooms[r]
                    await rooms[r].steal(ws)
                else:
                    await send(ws, { 'type': 'room_already_opened' })
                    await ws.close()
            else:
                rooms[r] = Room(r, ws)
                ws.userData['role'] = presenter_msg
                ws.userData['room'] = rooms[r]
        else:
            raise Kick()
    else:
        raise Kick()

