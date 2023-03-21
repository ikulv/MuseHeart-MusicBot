from __future__ import annotations
import asyncio
import json
import logging
from traceback import print_exc
from typing import TYPE_CHECKING, Optional
from os import environ
import aiohttp
import disnake
import tornado.ioloop
import tornado.web
import tornado.websocket
from async_timeout import timeout

if TYPE_CHECKING:
    from utils.client import BotPool

logging.getLogger('tornado.access').disabled = True

users_ws = {}
bots_ws = []


class IndexHandler(tornado.web.RequestHandler):

    def initialize(self, bots: list):
        self.bots = bots
        self.text = ""
        self.preview = False

    async def prepare(self):

        if preview:=environ.get("VIDEO_PREVIEW"):
            self.text = f"""
            <html>
                <head>
                </head>
                <body>
                    <table border="1" style="width: 100%; height: 100%;">
                      <tr>
                          <td style="width: 100%; height: 100%;">
                            <iframe width="100%" height="100%"
                                src="{preview}">
                            </iframe><br>
                          </td>
                      </tr>
                    </table><br>
            
                    <table border="1">
                      <tr>
                          <td><b style="font-size: 30px;">Exemplo do suporte a multi-voice:</b></td>
                      </tr>
                      <tr>
                        <td>
                            <video width="100%" height="100%" controls>
                                <source src="https://user-images.githubusercontent.com/74823568/200150891-825f23d7-83e0-44c5-8524-1e8a61a01b5e.mp4" type="video/mp4">
                                Seu navegador não suporta a reprodução deste vídeo.
                            </video>
                        </td>
                      </tr>
                    </table><br>
            
                    <table border="1">
                      <tr>
                          <td><b style="font-size: 30px;">Exemplo com canal de song-request em palco com multiplos bots (função de stage_announce ativado):</b></td>
                      </tr>
                      <tr>
                        <td>
                            <video width="100%" height="100%" controls>
                                <source src="https://user-images.githubusercontent.com/74823568/220428141-9cba4e2f-6864-409d-868d-8d2f7d22a5b6.mp4" type="video/mp4">
                                Seu navegador não suporta a reprodução deste vídeo.
                            </video>
                        </td>
                      </tr>
                    </table><br>
            
                    <table border="1">
                      <tr>
                          <td><b style="font-size: 30px;">Exemplo com canal de song-request em canal de forum com múltiplos bots:</b></td>
                      </tr>
                      <tr>
                        <td>
                            <video width="100%" height="100%" controls>
                                <source src="https://user-images.githubusercontent.com/74823568/198839619-a90cf199-fca2-4432-a379-c99145f3d640.mp4" type="video/mp4">
                                Seu navegador não suporta a reprodução deste vídeo.
                            </video>
                        </td>
                      </tr>
                    </table>
                </body>
            </html>
            """

            self.preview = True
            return

        cells = ""

        for bot in self.bots:

            try:
                async with timeout(7):
                    await bot.wait_until_ready()
            except asyncio.TimeoutError:
                continue

            if str(bot.user.id) in bot.config['INTERACTION_BOTS_CONTROLLER']:
                continue

            avatar = bot.user.display_avatar.replace(size=256, static_format="png").url

            cells += f"<tr><td><img src=\"{avatar}\" width=128 weight=128></img></td>\n" \
                     f"<td style=\"padding-top: 10px ; padding-bottom: 10px; padding-left: 10px; padding-right: 10px\">" \
                     f"Adicionar:<br><a href=\"{disnake.utils.oauth_url(bot.user.id, permissions=disnake.Permissions(bot.config['INVITE_PERMISSIONS']), scopes=('bot', 'applications.commands'))}\" " \
                     f"target=\"_blank\">{bot.user}</a></td></tr>"

        if not cells:

            try:
                killing_state = self.bots[0].pool.killing_state
            except:
                killing_state = False

            if killing_state is True:
                self.text = '<h1 style=\"font-size:5vw\">A aplicação será reiniciada em breve...</h1>'
            else:
                self.text = '<h1 style=\"font-size:5vw\">Não há bots disponíveis no momento...</h1>\n' \
                            '<br>(se o seu bot não apareceu na lista, verifique o erro que apareceu no terminal/console)'

        else:

            style = """<style>
            table, th, td {
                border:1px solid black;
                text-align: center;
            }
            </style>"""

            self.text = f"<p style=\"font-size:30px\">Bots Disponíveis:</p>{style}\n<table>{cells}</table>"

    def get(self):

        if self.preview:
            self.write(self.text)
            return

        try:
            # repl.it stuff
            ws_url = f"<p style=\"color:blue\">wss://{environ['REPL_SLUG']}.{environ['REPL_OWNER']}.repl.co:443/ws</p>"
        except KeyError:
            ws_url = "<Body onLoad=\" rpcUrl()\" ><p id=\"url\" style=\"color:blue\"></p><script>function rpcUrl(){document." \
                     "getElementById(\"url\").innerHTML = window.location.href.replace(\"http\", \"ws\")" \
                     ".replace(\"https\", \"wss\") + \"ws\"}</script></body>"


        self.write(f"{self.text}<p><a href=\"https://github.com/zRitsu/DC-MusicBot-RPC"
                   f"/releases\" target=\"_blank\">Baixe o app de rich presence aqui.</a></p>Link para adicionar no app "
                   f"de RPC abaixo: {ws_url}<br>Não esqueça de obter o token para configurar no app, use o comando /rich_presence para obter um.")
        # self.render("index.html") #será implementado futuramente...


class WebSocketHandler(tornado.websocket.WebSocketHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_ids: list = []
        self.bot_ids: list = []
        self.token = ""

    def on_message(self, message):

        data = json.loads(message)

        ws_id = data.get("user_ids")
        bot_id = data.get("bot_id")
        token = data.get("token", "")

        if not ws_id:

            if not bot_id:
                print(f"desconectando: por falta de id de usuario {self.request.remote_ip}\nDados: {data}")
                self.close(code=1005, reason="Desconectando: por falta de ids de usuario")
                return

            try:

                if users_ws[data["user"]].token != data["token"]:
                    print("rpc:", users_ws[data["user"]].token, "bot:", data["token"])
                    return

                users_ws[data["user"]].write_message(json.dumps(data))
            except KeyError:
                pass
            except Exception as e:
                print(f"Erro ao processar dados do rpc para o user [{data['user']}]: {repr(e)}")
            return

        is_bot = data.pop("bot", False)

        if is_bot:
            print(f"Nova conexão - Bot: {ws_id} {self.request.remote_ip}")
            self.bot_ids = ws_id
            bots_ws.append(self)
            return

        if len(ws_id) > 3:
            self.close(code=403, reason="Você está tentando conectar mais de 3 usuários consecutivamente...")
            return

        elif len(token) != 50:
            self.close(code=403, reason="O token tem que ter 50 caracteres!")
            return

        self.user_ids = ws_id

        print("\n".join(f"Nova conexão - User: {u}" for u in self.user_ids))

        for u_id in ws_id:
            try:
                users_ws[u_id].close(code=403, reason="Nova sessão iniciada...")
            except:
                pass
            users_ws[u_id] = self

        self.token = data.get('token', "")

        for w in bots_ws:
            try:
                w.write_message(json.dumps(data))
            except Exception as e:
                print(f"Erro ao processar dados do rpc para os bot's {w.bot_ids}: {repr(e)}")

    def check_origin(self, origin: str):
        return True

    def on_close(self):

        if self.user_ids:
            print("\n".join(f"Conexão Finalizada - User: {u}" for u in self.user_ids))
            for u_id in self.user_ids:
                try:
                    del users_ws[u_id]
                except KeyError:
                    continue
            return

        if not self.bot_ids:
            print(f"Conexão Finalizada - IP: {self.request.remote_ip}")

        else:

            print(f"Conexão Finalizada - Bot ID's: {self.bot_ids}")

            data = {"op": "close", "bot_id": self.bot_ids}

            for w in users_ws.values():
                try:
                    w.write_message(data)
                except Exception as e:
                    print(f"Erro ao processar dados do rpc para os usuários: [{', '.join(str(i) for i in w.user_ids)}]: {repr(e)}")

        bots_ws.remove(self)


class WSClient:

    def __init__(self, url: str, pool: BotPool):
        self.url: str = url
        self.pool = pool
        self.connection = None
        self.backoff: int = 7
        self.data: dict = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.connect_task = []

    async def connect(self):

        if not self.session:
            self.session = aiohttp.ClientSession()

        self.connection = await self.session.ws_connect(self.url, heartbeat=30)

        self.backoff = 7

        print("RPC client conectado, sincronizando rpc dos bots...")

        self.connect_task = [asyncio.create_task(self.connect_bot_rpc())]

    @property
    def is_connected(self):
        return self.connection and not self.connection.closed

    async def connect_bot_rpc(self):

        bot_ids = []

        for bot in self.pool.bots:

            try:
                bot_ids.append(bot.user.id)
            except:
                await bot.wait_until_ready()
                bot_ids.append(bot.user.id)

        await self.send({"user_ids": bot_ids, "bot": True})

        await asyncio.sleep(1)

        for bot in self.pool.bots:
            for player in bot.music.players.values():
                if player.last_channel.voice_states:
                    player.process_rpc(player.last_channel)

        print(f"[RPC client] - Os dados de rpc foram sincronizados com sucesso.")

    async def send(self, data: dict):

        if not self.is_connected:
            return

        try:
            await self.connection.send_json(data)
        except:
            print_exc()

    def clear_tasks(self):

        for t in self.connect_task:
            try:
                t.cancel()
            except:
                continue

        self.connect_task.clear()

    async def ws_loop(self):

        while True:

            try:

                if not self.is_connected:
                    self.clear_tasks()
                    await self.connect()

            except Exception as e:
                if isinstance(e, aiohttp.WSServerHandshakeError):
                    print(f"Falha ao conectar no servidor RPC, tentando novamente em {int(self.backoff)} segundo(s).")
                else:
                    print(f"Conexão com servidor RPC perdida - Reconectando em {int(self.backoff)} segundo(s).")

                await asyncio.sleep(self.backoff)
                self.backoff *= 2.5
                continue

            message = await self.connection.receive()

            if message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                print(f"RPC Websocket Closed: {message.extra}\nReconnecting in {self.backoff}s")
                await asyncio.sleep(self.backoff)
                continue

            data = json.loads(message.data)

            users: list = data.get("user_ids")

            if not users:
                continue

            op = data.get("op")

            if op == "rpc_update":

                for bot in self.pool.bots:
                    for player in bot.music.players.values():
                        if not player.last_channel:
                            continue
                        vc_user_ids = [i for i in player.last_channel.voice_states if i in users]
                        if vc_user_ids:
                            player.process_rpc(player.last_channel)
                            for i in vc_user_ids:
                                users.remove(i)


def run_app(bots: Optional[list] = None):

    bots = bots or []

    app = tornado.web.Application([
        (r'/', IndexHandler, {'bots': bots}),
        (r'/ws', WebSocketHandler),
    ])

    app.listen(port=environ.get("PORT", 80))


def start(bots: Optional[list] = None):
    run_app(bots)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    start()
