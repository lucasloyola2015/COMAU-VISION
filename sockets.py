from typing import Optional

try:
    from flask_socketio import SocketIO
except Exception:
    SocketIO = None  # type: ignore

socketio: Optional["SocketIO"] = None


def init_socketio(app, cors_allowed_origins="*", async_mode="threading"):
    global socketio
    if SocketIO is None:
        raise RuntimeError("flask_socketio no está disponible")
    if socketio is None:
        socketio = SocketIO(app, cors_allowed_origins=cors_allowed_origins, async_mode=async_mode)
    return socketio


