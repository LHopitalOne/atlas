import unittest

from atlas_bridge.core.http import Protocol

from .support import extract


def sends(ex):
    return sorted((str(c.path), c.line) for c in ex.calls if c.protocol == Protocol.WEBSOCKET)


def receives(ex):
    return sorted((str(r.path), r.line, r.handler) for r in ex.routes if r.protocol == Protocol.WEBSOCKET)


class NamespaceClassTest(unittest.TestCase):
    def test_handlers_and_emits_of_a_namespace_given_to_super(self):
        ex = extract(
            {
                'bot/events.py': """
                from enum import StrEnum
                ROOM = '/lobby'
                class Event(StrEnum):
                    ENTER = 'enter'
                    SAY = 'say'
                """,
                'bot/client.py': """
                import socketio
                from bot.events import ROOM, Event

                class Lobby(socketio.AsyncClientNamespace):
                    def __init__(self, name):
                        super().__init__(ROOM)
                        self.name = name

                    async def on_connect(self):
                        await self.emit(Event.ENTER, {'name': self.name})

                    async def on_say(self, data):
                        await self.emit(Event.SAY, data, namespace='/echo')
                        await self.send('hi')

                    def helper(self):
                        def on_inner():
                            pass
                """,
            }
        )
        self.assertEqual(sends(ex), [('/echo:say', 14), ('/lobby:enter', 11), ('/lobby:message', 15)])
        self.assertEqual(receives(ex), [('/lobby:say', 13, 'Lobby.on_say')])

    def test_namespace_given_where_the_class_is_made(self):
        ex = extract(
            {
                'app/chat.py': """
                from socketio import Namespace, Server

                class Chat(Namespace):
                    def on_message(self, sid, data):
                        self.emit('reply', data, room=sid)

                class Plain(Namespace):
                    def on_ping(self, sid):
                        pass

                sio = Server()
                sio.register_namespace(Chat('/chat'))
                sio.register_namespace(Plain())
                """,
            }
        )
        self.assertEqual(sends(ex), [('/chat:reply', 6)])
        self.assertEqual(receives(ex), [('/:ping', 9, 'Plain.on_ping'), ('/chat:message', 5, 'Chat.on_message')])

    def test_unknown_namespace_is_no_channel(self):
        ex = extract(
            {
                'app/chat.py': """
                import os
                import socketio

                class Chat(socketio.ClientNamespace):
                    def on_reply(self, data):
                        self.emit('ack')

                client = socketio.Client()
                client.register_namespace(Chat(os.environ['NAMESPACE']))
                """,
            }
        )
        self.assertEqual((sends(ex), receives(ex)), ([], []))


class ClientAndServerObjectTest(unittest.TestCase):
    def test_decorators_and_emits(self):
        ex = extract(
            {
                'app/server.py': """
                import socketio

                sio = socketio.AsyncServer(async_mode='asgi')

                @sio.event
                async def connect(sid, environ):
                    pass

                @sio.event
                async def chat(sid, data):
                    await sio.emit('chat', data, skip_sid=sid)

                @sio.on('join', namespace='/rooms')
                async def joined(sid, data):
                    await sio.emit('joined', data, namespace='/rooms')

                async def typing(sid):
                    pass

                sio.on('typing', typing)
                """,
            }
        )
        self.assertEqual(sends(ex), [('/:chat', 12), ('/rooms:joined', 16)])
        self.assertEqual(receives(ex), [('/:chat', 11, 'chat'), ('/:typing', 21, ''), ('/rooms:join', 15, 'joined')])

    def test_emit_on_other_objects_is_no_channel(self):
        ex = extract(
            {
                'app/bus.py': """
                import socketio
                from pyee import EventEmitter

                bus = EventEmitter()
                bus.emit('chat', 1)

                @bus.on('chat')
                def chat(data):
                    pass
                """,
            }
        )
        self.assertEqual((sends(ex), receives(ex)), ([], []))


if __name__ == '__main__':
    unittest.main()
