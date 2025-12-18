from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from repository.drive_repository import get_drive_repository
from repository.document_repository import get_document_repository
from services.api_service.schemas import (
    CreateDocumentRequest,
    ManualTriggerRequest,
    UpdateMetadataRequest,
)

router = APIRouter(prefix="/api/v1", tags=["documents"])

drive_repo = get_drive_repository()
document_repo = get_document_repository()


@router.post("/trigger")
async def manual_trigger(request: ManualTriggerRequest):
    """Verify document exists (messages are processed immediately)."""
    doc_id = request.doc_id

    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id required")

    try:
        drive_repo.get_document_content(doc_id)
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"Document {doc_id} not found: {exc}"
        )

    return {
        "status": "success",
        "doc_id": doc_id,
        "message": "Document exists. Messages are processed immediately when received.",
    }


@router.get("/versions/{doc_id}")
async def get_versions(doc_id: str):
    """List all versions for a document."""
    versions = document_repo.list_versions(doc_id)
    return {"doc_id": doc_id, "versions": versions}


@router.get("/versions/{doc_id}/{version_id}")
async def get_version(doc_id: str, version_id: str):
    """Get a specific document version."""
    version_data = document_repo.load_version(doc_id, version_id)
    if not version_data:
        raise HTTPException(status_code=404, detail="Version not found")
    return version_data


@router.post("/revert/{doc_id}/{version_id}")
async def revert_to_version(doc_id: str, version_id: str):
    """Revert document to a previous version."""
    version_data = document_repo.load_version(doc_id, version_id)
    if not version_data:
        raise HTTPException(status_code=404, detail="Version not found")

    content = version_data.get("content", "")

    try:
        drive_repo.update_document_content(doc_id, content)
        document_repo.update_vector_db(doc_id, content)

        return {
            "status": "success",
            "message": f"Document reverted to version {version_id}",
            "doc_id": doc_id,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error reverting document: {exc}"
        )


@router.get("/status")
async def get_status():
    """Get service status."""
    return {
        "service": "Epimetheus API Service",
        "message": "Service is running. Messages are processed immediately without batching.",
    }


@router.get("/documents")
async def list_documents(
    folder_id: Optional[str] = Query(None, description="Filter by folder ID")
):
    """List all documents in the Drive folder."""
    try:
        docs = document_repo.get_documents_from_mapping(folder_id)
        return {"documents": docs, "folder_id": folder_id or document_repo.folder_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {exc}")


@router.get("/documents/search")
async def search_docs(
    query: str = Query(..., description="Search query"),
    folder_id: Optional[str] = Query(None, description="Filter by folder ID"),
):
    """Search for documents by name or content."""
    try:
        results = document_repo.search_documents(query, folder_id)
        return {"query": query, "results": results, "count": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error searching documents: {exc}")


@router.post("/documents")
async def create_doc(request: CreateDocumentRequest):
    """Create a new document in the Drive folder."""
    try:
        doc = drive_repo.create_document(
            name=request.name,
            folder_id=request.folder_id,
            initial_content=request.initial_content or "",
        )

        if request.tags or request.description:
            document_repo.save_metadata(
                doc_id=doc["id"],
                name=request.name,
                folder_id=doc.get("folder_id"),
                tags=request.tags,
                description=request.description,
            )

        return {"status": "success", "document": doc}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error creating document: {exc}")


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get document content and metadata."""
    try:
        content = drive_repo.get_document_content(doc_id)
        metadata = document_repo.get_metadata(doc_id)

        return {"doc_id": doc_id, "content": content, "metadata": metadata}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error reading document: {exc}")


@router.get("/documents/{doc_id}/metadata")
async def get_metadata(doc_id: str):
    """Get document metadata."""
    metadata = document_repo.get_metadata(doc_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Document metadata not found")
    return metadata


@router.put("/documents/{doc_id}/metadata")
async def update_metadata(doc_id: str, request: UpdateMetadataRequest):
    """Update document metadata."""
    try:
        existing = document_repo.get_metadata(doc_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")

        document_repo.save_metadata(
            doc_id=doc_id,
            name=request.name or existing.get("name", ""),
            folder_id=existing.get("folder_id"),
            tags=request.tags if request.tags is not None else existing.get("tags", []),
            description=request.description
            if request.description is not None
            else existing.get("description", ""),
        )

        return {"status": "success", "message": "Metadata updated"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error updating metadata: {exc}"
        )


@router.get("/documents/metadata/all")
async def get_all_metadata(
    folder_id: Optional[str] = Query(None, description="Filter by folder ID")
):
    """Get metadata for all documents."""
    try:
        metadata_list = document_repo.get_all_metadata(folder_id)
        return {"documents": metadata_list, "count": len(metadata_list)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error retrieving metadata: {exc}")


@router.get("/drive/mapping")
async def get_drive_mapping(
    folder_id: Optional[str] = Query(None, description="Filter by folder ID")
):
    """Get all documents from the Drive mapping collection."""
    try:
        documents = document_repo.get_drive_mapping(folder_id=folder_id)
        return {
            "status": "success",
            "documents": documents,
            "count": len(documents),
            "folder_id": folder_id,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving mapping: {exc}"
        )


@router.post("/drive/mapping/sync")
async def sync_drive_mapping(
    folder_id: Optional[str] = Query(
        None, description="Folder ID to sync (defaults to configured folder)"
    )
):
    """Sync Drive folder contents to MongoDB mapping."""
    try:
        result = document_repo.sync_drive_folder_to_mapping(folder_id)
        return {
            "status": "success",
            "message": "Drive folder synced successfully",
            "folder_id": result.get("folder_id"),
            "document_count": result.get("document_count", 0),
            "synced_at": result.get("synced_at"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error syncing Drive folder: {exc}")


@router.put("/drive/mapping/document")
async def update_drive_document(
    doc_id: str = Query(..., description="Document ID"),
    name: str = Query(..., description="Document name"),
    folder_id: str = Query(..., description="Folder ID"),
):
    """Manually update a single document in the Drive mapping."""
    try:
        document = document_repo.upsert_drive_document(
            doc_id=doc_id, name=name, folder_id=folder_id
        )
        return {
            "status": "success",
            "message": "Document updated successfully",
            "document": document,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error updating document: {exc}"
        )
