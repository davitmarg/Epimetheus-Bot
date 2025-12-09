"""
Epimetheus Bot - Main Entry Point

Orchestrates all services:
1. Message Listener Bot - receives all messages and queues them
2. Mention Listener Bot - receives mentions and replies using agentic behavior
3. Updater Service - checks last x messages and decides if knowledge base updates are needed
4. API Service - REST API endpoints
"""

import multiprocessing
import threading
import sys
import uvicorn
from dotenv import load_dotenv
from services.updater_service import start as start_updater_service
from services.bot import start as start_bot_service
from services.api_service import app as api_app
from repository.document_repository import get_document_repository

load_dotenv()


def initialize():
    """Sync Drive folder mapping on startup"""
    try:
        print("Syncing Drive folder mapping on startup...")
        document_repo = get_document_repository()
        mapping = document_repo.sync_drive_folder_to_mapping()
        print(
            f"Drive folder synced successfully. Found {len(mapping.get('documents', []))} documents."
        )
    except Exception as e:
        print(f"Warning: Failed to sync Drive folder on startup: {str(e)}")
        print("You can manually sync using: POST /api/v1/drive/mapping/sync")


if __name__ == "__main__":
    # Check command line arguments to determine which service to run
    if len(sys.argv) > 1:
        service = sys.argv[1].lower()

        if service == "bot":
            print("Starting Message/Mention Listener Bot only...")
            start_bot_service()
        elif service == "updater":
            print("Starting Updater Service only...")
            initialize()
            start_updater_service()
        elif service == "api":
            print("Starting API Service on http://0.0.0.0:8000")
            uvicorn.run(api_app, host="0.0.0.0", port=8000, log_level="info")
        else:
            print(f"Unknown service: {service}")
            print("Usage: python main.py [bot|updater|api]")
            sys.exit(1)
    else:
        # Default: Run all services
        print("Starting Project Epimetheus (all services)...")

        # Sync Drive folder mapping before starting services
        initialize()

        # Start Bot Service in a background process
        bot_service_process = multiprocessing.Process(target=start_bot_service)
        bot_service_process.start()

        # Start the Updater Service in a background thread
        updater_thread = threading.Thread(target=start_updater_service, daemon=True)
        updater_thread.start()

        # Start the API Service in the main thread (blocking)
        print("Starting Epimetheus API Service on http://0.0.0.0:8000")
        uvicorn.run(api_app, host="0.0.0.0", port=8000, log_level="info")
