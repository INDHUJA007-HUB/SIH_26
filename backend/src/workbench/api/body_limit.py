"""Bound JSON command bodies before decoding; file bytes use direct S3 grants."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class CommandBodyLimit:
    def __init__(self, app: ASGIApp, limit: int = 1024 * 1024) -> None:
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH", "PUT"}:
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                await JSONResponse(
                    {
                        "code": "COMMAND_TOO_LARGE",
                        "status": 413,
                        "title": "Command body exceeds the configured limit",
                    },
                    status_code=413,
                )(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
