#!/usr/bin/env python3

import sys
import os
import time
import json
import aiohttp
from aiohttp import web, hdrs
from urllib.parse import quote
import asyncio
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from app import websocket_json_msg, Kick

allowed_origin_hosts = None
stylestamp = str(int(os.path.getmtime('web/design/style.css')))

async def http_root_handler(request):
    with open('web/templates/index.html') as f:
        return web.Response(text=f.read().replace('{{STYLESTAMP}}', stylestamp), content_type='text/html')

async def http_redirect_home(request):
    raise web.HTTPFound(location='/')

async def http_app_handler(request):
    data = await request.post()
    if not 'room' in data: raise web.HTTPFound(location='/')
    if 'presenter' in data:
        with open('web/templates/control.html') as f:
            return web.Response(text=f.read().replace('{{ROOM}}', quote(data['room'])).replace('{{STYLESTAMP}}', stylestamp), content_type='text/html')
    else:
        with open('web/templates/room.html') as f:
            return web.Response(text=f.read().replace('{{ROOM}}', quote(data['room'])).replace('{{STYLESTAMP}}', stylestamp), content_type='text/html')

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
        web.get('/index.html', http_redirect_home),
        web.get('/room.html', http_redirect_home),
        web.get('/control.html', http_redirect_home),
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
