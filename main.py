from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import webhook
import cron
import checkin_web
import dashboard
from database import init_pool, close_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(lifespan=lifespan)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(webhook.router)
app.include_router(cron.router)
app.include_router(checkin_web.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
