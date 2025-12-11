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
from dotenv import load_dotenv
from services.updater_service import start as start_updater_service
from services.bot import start as start_bot_service
from services.api_service import start as start_api_service

load_dotenv()


if __name__ == "__main__":
    # Check command line arguments to determine which service to run
    if len(sys.argv) > 1:
        service = sys.argv[1].lower()

        if service == "bot":
            print("Starting Message/Mention Listener Bot only...")
            start_bot_service()
        elif service == "updater":
            print("Starting Updater Service only...")
            start_updater_service()
        elif service == "api":
            print("Starting API Service on http://0.0.0.0:8000")
            start_api_service()
        else:
            print(f"Unknown service: {service}")
            print("Usage: python main.py [bot|updater|api]")
            sys.exit(1)
    else:
        # Default: Run all services
        print("Starting Project Epimetheus (all services)...")

        # Start Bot Service in a background process
        bot_service_process = multiprocessing.Process(target=start_bot_service)
        bot_service_process.start()

        # Start the Updater Service in a background thread
        updater_thread = threading.Thread(target=start_updater_service, daemon=True)
        updater_thread.start()

        # Start the API Service in the main thread (blocking)
        print("Starting Epimetheus API Service on http://0.0.0.0:8000")
        start_api_service()
