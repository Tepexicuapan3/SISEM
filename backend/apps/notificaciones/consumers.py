"""Canal de tiempo real de notificaciones.

El consumer base ya une cada socket al grupo `user.{id}`; las notificaciones
se publican solo a ese grupo, asi que cada usuario recibe unicamente las suyas.
No ejecuta ninguna decision: el frontend solo refresca su bandeja.
"""
from apps.realtime.consumers.base import BaseRealtimeConsumer


class NotificacionesConsumer(BaseRealtimeConsumer):
    pass
