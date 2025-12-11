import os
import pytest
from repository.drive_repository import DriveRepository
from repository.document_repository import DocumentRepository
from utils.db_utils import get_mongodb_db


def _has_google_env():
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH")
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    return bool(folder_id) and bool(creds_path) and os.path.exists(creds_path)


def _has_mongo():
    try:
        return get_mongodb_db() is not None
    except Exception:
        return False


@pytest.mark.integration
def test_drive_repository_lists_documents_with_real_env():
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured for integration test")

    drive_repo = DriveRepository()
    docs = drive_repo.list_documents_in_folder()

    assert isinstance(docs, list)
    assert len(docs) > 0
    # Not asserting non-empty because folder may legitimately be empty
    print('Docs: ', docs)

@pytest.mark.integration
def test_document_repository_syncs_drive_mapping_into_mongo():
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured for integration test")
    if not _has_mongo():
        pytest.skip("MongoDB not reachable for integration test")

    repo = DocumentRepository()
    summary = repo.sync_drive_folder_to_mapping()

    assert summary.get("folder_id") == repo.folder_id
    assert isinstance(summary.get("documents"), list)

    mapping = repo.get_drive_mapping()
    assert isinstance(mapping, list)
    assert len(mapping) > 0
    print('Mapping: ', mapping)
    print('Mapping length: ', len(mapping))
    print('Summary: ', summary)
    print('Summary folder_id: ', summary.get("folder_id"))
    print('Summary documents: ', summary.get("documents"))
    print('Summary document_count: ', summary.get("document_count"))
    print('Summary synced_at: ', summary.get("synced_at"))
