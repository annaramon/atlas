from fastapi import FastAPI

from app.api import ask

app = FastAPI(title="Atlas")

app.include_router(ask.router)
