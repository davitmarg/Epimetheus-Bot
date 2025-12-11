import uvicorn

from services.api_service import app


def start(host: str = "0.0.0.0", port: int = 8000):
    """Start the API service with uvicorn."""
    uvicorn.run(app, host=host, port=port, log_level="info")


__all__ = ["start"]
