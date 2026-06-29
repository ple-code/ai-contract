from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import auth, contracts, reviews, clauses, versions, legal, admin, rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="明衡 · 合同审核 AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(auth.me_router)
app.include_router(contracts.router)
app.include_router(reviews.router)
app.include_router(clauses.router)
app.include_router(versions.router)
app.include_router(legal.router)
app.include_router(admin.router)
app.include_router(rules.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
