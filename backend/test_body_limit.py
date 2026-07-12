"""Body-ceiling enforcement, including the chunked (no Content-Length) case
that the header fast-path cannot catch."""
import asyncio

from operational import BodySizeLimitMiddleware


def _drive(middleware, scope, incoming_messages):
    sent = []

    incoming = iter(incoming_messages)

    async def receive():
        try:
            return next(incoming)
        except StopIteration:
            return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))
    return sent


async def _ok_app(scope, receive, send):
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    await send({"type": "http.response.start", "status": 200, "headers": [(b"x-body-len", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": b"ok"})


HTTP_SCOPE = {"type": "http", "method": "POST", "path": "/score", "headers": []}


def test_rejects_oversize_chunked_body_without_content_length():
    middleware = BodySizeLimitMiddleware(_ok_app, max_bytes=1024)
    chunks = [
        {"type": "http.request", "body": b"x" * 500, "more_body": True},
        {"type": "http.request", "body": b"x" * 500, "more_body": True},
        {"type": "http.request", "body": b"x" * 500, "more_body": True},  # 1500 > 1024
        {"type": "http.request", "body": b"", "more_body": False},
    ]
    sent = _drive(middleware, HTTP_SCOPE, chunks)
    starts = [m["status"] for m in sent if m["type"] == "http.response.start"]
    assert starts == [413]


def test_passes_small_body_through_intact():
    middleware = BodySizeLimitMiddleware(_ok_app, max_bytes=1024)
    chunks = [
        {"type": "http.request", "body": b"hello ", "more_body": True},
        {"type": "http.request", "body": b"world", "more_body": False},
    ]
    sent = _drive(middleware, HTTP_SCOPE, chunks)
    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 200
    # The handler received the full, correctly reassembled body.
    header = dict(start["headers"])
    assert header[b"x-body-len"] == b"11"
