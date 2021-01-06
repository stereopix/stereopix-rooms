#!/usr/bin/env python3

import sys
import os
import json
import aiohttp
from aiohttp import web, hdrs
import asyncio
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from app import websocket_json_msg

allowed_origin_hosts = None

async def http_root_handler(request):
    with open('web/index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')

async def websocket_handler(request): 
    if allowed_origin_hosts and request.headers.get(hdrs.ORIGIN) not in allowed_origin_hosts:
        raise HTTPForbidden()

    ws = web.WebSocketResponse()
    ws.userData = {}
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            if msg.data == 'bye':
                await ws.close()
            else:
                try:
                    j = json.loads(msg.data)
                    await websocket_json_msg(ws, j)
                except json.decoder.JSONDecodeError:
                    await ws.send_str(json.dumps({'type': 'kick' }))
                    await ws.close()
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print('ws connection closed with exception %s' % ws.exception())

    await websocket_json_msg(ws, { 'type': 'connection_closed' })
    return ws


async def start_server(host, port):
    app = web.Application()
    app.add_routes([
        web.get('/ws', websocket_handler),
        web.get('/', http_root_handler),
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
