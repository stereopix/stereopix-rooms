Stereopix ROOMS
===============

Application to allow people to look at stereoscopic images synchronously with the viewer of https://stereopix.net/

Demo
----

A live demo is hosted by repl.it: https://rooms.stereopix.repl.co/

Development
-----------

Dependencies
""""""""""""

* ``aiohttp`` python3 module (``pip install aiohttp``)

Run & test
""""""""""

In the root of the repository, launch ``python3 ./app/server.py`` and connect to http://localhost:8080/ with your browser.

Structure
"""""""""

The most important parts are in ``web/`` directory for static files and in ``app/app.py`` for the messaging server.
