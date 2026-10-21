from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.realtime.auth import REALTIME_QUERY_TOKEN_SCOPE_KEY, REALTIME_USER_SCOPE_KEY

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403


class BaseRealtimeConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if self.scope.get(REALTIME_QUERY_TOKEN_SCOPE_KEY):
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        user = self.scope.get(REALTIME_USER_SCOPE_KEY)
        if user is None:
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        if not self.authorize_scope(user):
            await self.close(code=WS_CLOSE_FORBIDDEN)
            return

        self._joined_groups = []
        # Grupo por usuario: permite cortar el socket al revocar su sesion.
        group_names = [f"user.{user['id']}", *self.get_group_names()]
        for group_name in group_names:
            await self.channel_layer.group_add(group_name, self.channel_name)
            self._joined_groups.append(group_name)

        await self.accept()

    async def disconnect(self, code):
        joined_groups = getattr(self, "_joined_groups", [])
        for group_name in joined_groups:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def realtime_event(self, event):
        payload = event.get("event", {})
        await self.send_json(payload)

    async def session_revoked(self, event):
        # Sesion revocada (admin/reset/desactivacion): se corta el socket.
        await self.close(code=WS_CLOSE_UNAUTHORIZED)

    def get_group_names(self) -> list[str]:
        return []

    def authorize_scope(self, realtime_user) -> bool:
        return True
