"""
Proof Social - Instagram OAuth API
API para autenticação OAuth com Meta/Instagram
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth

app = FastAPI(
    title="Proof Social Instagram Auth API",
    description="API para autenticação OAuth com Meta/Instagram",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])


@app.get("/")
async def root():
    return {
        "message": "Proof Social Instagram Auth API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}

