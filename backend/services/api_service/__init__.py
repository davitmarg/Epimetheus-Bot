from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api_service.routes import router

load_dotenv()

app = FastAPI(title="Epimetheus API Service")

# Configure CORS to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend URL(s)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

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
