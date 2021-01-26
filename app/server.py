#!/usr/bin/env python3

import sys
import os
import time
import json
import aiohttp
from aiohttp import web, hdrs
from urllib.parse import quote, quote_plus, unquote_plus
import asyncio
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from app import websocket_json_msg, is_opened, Kick

allowed_origin_hosts = None
stylestamp = str(int(os.path.getmtime('web/design/style.css')))

async def simple_template(filename, d=None):
    repl = {'STYLESTAMP': stylestamp, 'ROOM': ''}
    if d: repl.update(d)
    with open('web/templates/' + filename + '.html', 'r') as f:
        txt = f.read()
        for k, v in repl.items():
            txt = txt.replace('{{'+k+'}}', v)
        return web.Response(text=txt, content_type='text/html')

async def http_root_handler(request):
    return await simple_template('index')

async def http_room_handler(request):
    request.match_info['room'] = unquote_plus(request.match_info['room'])
    if is_opened(request.match_info['room']):
        return await app_handler(request.match_info)
    return await simple_template('closed_room', {'ROOM': quote(request.match_info['room'])})

async def http_app_handler(request):
    data = await request.post()
    if 'room' in data and not 'presenter' in data:
        raise web.HTTPFound(location='/'+quote_plus(data['room']))
    return await app_handler(data)

async def app_handler(data):
    if not 'room' in data: raise web.HTTPFound(location='/')
    if 'presenter' in data:
        return await simple_template('control', {'ROOM': quote(data['room'])})
    else:
        return await simple_template('room', {'ROOM': quote(data['room'])})

async def websocket_handler(request): 
    if allowed_origin_hosts and request.headers.get(hdrs.ORIGIN) not in allowed_origin_hosts:
        raise web.HTTPForbidden()

    ws = web.WebSocketResponse(autoping=False)
    ws.userData = {}
    await ws.prepare(request)

    async def heatbeat():
        async def heatbeat_ping():
            try:
                await ws.ping()
            except ConnectionResetError:
                ws.userData['lastmsg'] = -1
                await websocket_json_msg(ws, { 'type': 'connection_closed', 'cause': 'heatbeat_ping' })

        while True:
            await asyncio.sleep(10)
            if ws.closed or ws.userData['lastmsg'] < 0: return
            dt = time.time() - ws.userData['lastmsg']
            if dt > 39:
                ws.force_close()
                ws.userData['lastmsg'] = -1
                await websocket_json_msg(ws, { 'type': 'connection_closed', 'cause': 'heatbeat_no_pong' })
                return
            elif dt > 19:
                asyncio.create_task(heatbeat_ping())

    asyncio.create_task(heatbeat())

    async for msg in ws:
        ws.userData['lastmsg'] = time.time()
        if msg.type == aiohttp.WSMsgType.TEXT:
            if msg.data == 'bye':
                await ws.close()
            else:
                try:
                    j = json.loads(msg.data)
                    await websocket_json_msg(ws, j)
                except (json.decoder.JSONDecodeError, Kick):
                    if not ws.closed:
                        msg = {'type': 'kick' }
                        print('>', msg)
                        await ws.send_str(json.dumps(msg))
                        await ws.close()

        elif msg.type == aiohttp.WSMsgType.ERROR:
            print('ws connection closed with exception %s' % ws.exception())

        elif msg.type == aiohttp.WSMsgType.PING:
            await ws.pong(msg.data)

    if not ws.userData['lastmsg'] < 0:
        ws.userData['lastmsg'] = -1
        await websocket_json_msg(ws, { 'type': 'connection_closed', 'cause': 'end_of_messages' })

    return ws

async def start_server(host, port):
    app = web.Application()
    app.add_routes([
        web.get('/ws', websocket_handler),
        web.get('/', http_root_handler),
        web.post('/', http_app_handler),
        web.get('/{room}', http_room_handler),
        web.get('/{room}/', http_room_handler),
        web.static('/', 'web'),
        ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f'Listening {host}:{port}')

if __name__ == '__main__':
    host = '0.0.0.0'
    port = 8080
    if len(sys.argv) >= 3:
        host = sys.argv[1]
        port = sys.argv[2]
        allowed_origin_hosts = sys.argv[3:]
    elif len(sys.argv) == 2:
        port = sys.argv[1]
    print('Allowed origins:', '*' if not allowed_origin_hosts else ', '.join(allowed_origin_hosts))
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start_server(host, port))
        loop.run_forever()
    except KeyboardInterrupt:
        print('Bye.')
