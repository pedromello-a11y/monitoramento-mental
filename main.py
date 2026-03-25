from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import init_pool, close_pool
import webhook
import cron
import checkin_web


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(lifespan=lifespan)
app.include_router(webhook.router)
app.include_router(cron.router)
app.include_router(checkin_web.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
