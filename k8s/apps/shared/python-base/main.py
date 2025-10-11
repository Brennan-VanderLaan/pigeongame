"""
Simple Hello World ASGI application
"""


async def app(scope, receive, send):
    """
    Simple ASGI application that responds with Hello World
    """
    if scope["type"] == "http":
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/plain"]],
        })
        await send({
            "type": "http.response.body",
            "body": b"Hello World from Python ASGI!\n",
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
