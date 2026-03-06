from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

from routes import auth, groups, expenses, invites, balances, settlements

app = FastAPI(title="SplitSmart API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "https://your-app-domain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(groups.router, prefix="/groups", tags=["Groups"])
app.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])
app.include_router(invites.router, tags=["Invites"])
app.include_router(balances.router, tags=["Balances"])
app.include_router(settlements.router, tags=["Settlements"])


@app.get("/health")
async def health():
    return {"status": "ok"}
