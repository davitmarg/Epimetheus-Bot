"""
Epimetheus Bot - Main Entry Point

Orchestrates all services: Bot, Updater, and API.
"""

import multiprocessing
import threading
import sys
import uvicorn
from dotenv import load_dotenv
from services.updater_service import start_updater_service
from services.bot.service import start as start_bot_service
from services.api_service import app as api_app
from repository.document_repository import sync_drive_folder_to_mapping

load_dotenv()


def initalize():
    """Sync Drive folder mapping on startup"""
    try:
        print("Syncing Drive folder mapping on startup...")
        mapping = sync_drive_folder_to_mapping()
        print(
            f"Drive folder synced successfully. Found {len(mapping.get('documents', []))} documents."
        )
    except Exception as e:
        print(f"Warning: Failed to sync Drive folder on startup: {str(e)}")
        print("You can manually sync using: POST /api/v1/drive/mapping/sync")


def start_updater_thread():
    """Start the updater service in a background thread"""
    print("Starting Epimetheus Updater Service (Redis Consumer)...")
    start_updater_service()


if __name__ == "__main__":
    # Check command line arguments to determine which service to run
    if len(sys.argv) > 1:
        service = sys.argv[1].lower()

        if service == "bot":
            print("Starting Project Epimetheus Bot only...")
            start_bot_service()
        elif service == "updater":
            print("Starting Project Epimetheus Updater Service only...")
            initalize()
            start_updater_service()
        elif service == "api":
            print("Starting Project Epimetheus API Service on http://0.0.0.0:8000")
            uvicorn.run(api_app, host="0.0.0.0", port=8000, log_level="info")
        else:
            print(f"Unknown service: {service}")
            print("Usage: python main.py [bot|updater|api]")
            print("  bot     - Run only the Slack bot")
            print("  updater - Run only the updater service (Redis consumer)")
            print("  api     - Run only the API service")
            sys.exit(1)
    else:
        # Default: Run all services
        print("Starting Project Epimetheus (all services)...")

        # Sync Drive folder mapping before starting services
        initalize()

        # Start the Bot in a background process (not thread cause the bot must run in main thread)
        bot_process = multiprocessing.Process(target=start_bot_service)
        bot_process.start()

        # Start the Updater Service in a background thread
        updater_thread = threading.Thread(target=start_updater_thread, daemon=True)
        updater_thread.start()

        # Start the API Service in the main thread (blocking)
        print("Starting Epimetheus API Service on http://0.0.0.0:8000")
        uvicorn.run(api_app, host="0.0.0.0", port=8000, log_level="info")
