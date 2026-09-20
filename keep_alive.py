from aiohttp import web


async def health(request):
    return web.Response(text="Loud & Clear bot is alive")


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    return app
