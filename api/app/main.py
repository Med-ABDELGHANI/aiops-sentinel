from fastapi import FastAPI

from app.routers import chat, incidents, servers, services

app = FastAPI(
    title="AIOps Sentinel API",
    description="API d'inventaire infrastructure et d'assistant IA (SQL + RAG)",
    version="1.0.0",
)

app.include_router(servers.router)
app.include_router(services.router)
app.include_router(incidents.router)
app.include_router(chat.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "AIOps Sentinel API"}
