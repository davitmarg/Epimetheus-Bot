"""
Entry Module
Handles Redis queue consumption and service startup.
"""

from repository.document_repository import get_document_repository

document_repo = get_document_repository()


def start():
    """Start the updater service consumer"""
    print("Starting Epimetheus Updater Service (Redis Consumer)...")
    try:
        print("Syncing Drive mapping to MongoDB before consumption...")
        document_repo.sync_drive_folder_to_mapping()
        print("✓ Drive mapping sync completed.")
    except Exception as e:
        print(f"✗ Drive mapping sync failed: {e}")
    document_repo.consume_from_redis()
