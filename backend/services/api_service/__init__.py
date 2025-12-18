from dotenv import load_dotenv
from fastapi import FastAPI

from services.api_service.routes import router

load_dotenv()

app = FastAPI(title="Epimetheus API Service")
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Epimetheus API Service"}


def start(host: str = "0.0.0.0", port: int = 8000):
    """Start the API service."""
    from services.api_service.entry import start as _start

    _start(host=host, port=port)


__all__ = ["app", "start"]
