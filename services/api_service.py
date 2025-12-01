"""
API Service

FastAPI service providing REST API endpoints for managing documents,
triggering updates, and checking service status.

Supports multiple dynamic documents in a Google Drive folder.
"""

from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Epimetheus API Service")

from services.updater_service import (
    document_stacks,
    process_document_update,
    list_document_versions,
    load_document_version,
    update_vector_db,
    CHAR_THRESHOLD,
    GOOGLE_DRIVE_FOLDER_ID,
)

from repository.drive_repository import (
    get_document_content,
    update_document_content,
    create_document
)
from repository.document_repository import (
    get_document_repository,
    search_documents,
    sync_drive_folder_to_mapping,
    get_documents_from_mapping
)


class ManualTriggerRequest(BaseModel):
    doc_id: Optional[str] = None  # If None, triggers all documents


class CreateDocumentRequest(BaseModel):
    name: str
    folder_id: Optional[str] = None
    initial_content: Optional[str] = ""
    tags: Optional[List[str]] = None
    description: Optional[str] = None


class UpdateMetadataRequest(BaseModel):
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None


@app.post("/api/v1/trigger")
async def manual_trigger(request: ManualTriggerRequest):
    """Manually trigger document generation"""
    doc_id = request.doc_id
    
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id required")
    
    if doc_id not in document_stacks:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found in stacks")
    
    # Process synchronously for API response
    process_document_update(doc_id, force=True)
    
    return {
        "status": "success",
        "doc_id": doc_id,
        "message": "Document update completed"
    }


@app.get("/api/v1/versions/{doc_id}")
async def get_versions(doc_id: str):
    """List all versions for a document"""
    versions = list_document_versions(doc_id)
    return {
        "doc_id": doc_id,
        "versions": versions
    }


@app.get("/api/v1/versions/{doc_id}/{version_id}")
async def get_version(doc_id: str, version_id: str):
    """Get a specific document version"""
    version_data = load_document_version(doc_id, version_id)
    if not version_data:
        raise HTTPException(status_code=404, detail="Version not found")
    return version_data


@app.post("/api/v1/revert/{doc_id}/{version_id}")
async def revert_to_version(doc_id: str, version_id: str):
    """Revert document to a previous version"""
    version_data = load_document_version(doc_id, version_id)
    if not version_data:
        raise HTTPException(status_code=404, detail="Version not found")
    
    content = version_data.get('content', '')
    
    try:
        update_document_content(doc_id, content)
        update_vector_db(doc_id, content)
        
        # Reset stack
        if doc_id in document_stacks:
            document_stacks[doc_id] = {
                'char_count': 0,
                'messages': [],
                'last_version': version_id
            }
        
        return {
            "status": "success",
            "message": f"Document reverted to version {version_id}",
            "doc_id": doc_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reverting document: {str(e)}")


@app.get("/api/v1/status")
async def get_status():
    """Get service status and document stack information"""
    status = {
        "service": "Epimetheus API Service",
        "documents": {}
    }
    
    for doc_id, stack in document_stacks.items():
        status["documents"][doc_id] = {
            "char_count": stack['char_count'],
            "message_count": len(stack['messages']),
            "threshold": CHAR_THRESHOLD,
            "last_version": stack.get('last_version')
        }
    
    return status


@app.get("/api/v1/documents")
async def list_documents(folder_id: Optional[str] = Query(None, description="Filter by folder ID")):
    """List all documents in the Drive folder"""
    try:
        docs = get_documents_from_mapping(folder_id)
        return {
            "documents": docs,
            "folder_id": folder_id or GOOGLE_DRIVE_FOLDER_ID
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@app.get("/api/v1/documents/search")
async def search_docs(query: str = Query(..., description="Search query"), 
                     folder_id: Optional[str] = Query(None, description="Filter by folder ID")):
    """Search for documents by name or content"""
    try:
        results = search_documents(query, folder_id)
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching documents: {str(e)}")


@app.post("/api/v1/documents")
async def create_doc(request: CreateDocumentRequest):
    """Create a new document in the Drive folder"""
    try:
        doc = create_document(
            name=request.name,
            folder_id=request.folder_id,
            initial_content=request.initial_content or ""
        )
        
        # Save metadata if provided
        if request.tags or request.description:
            repo = get_document_repository()
            repo.save_metadata(
                doc_id=doc['id'],
                name=request.name,
                folder_id=doc.get('folder_id'),
                tags=request.tags,
                description=request.description
            )
        
        return {
            "status": "success",
            "document": doc
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating document: {str(e)}")


@app.get("/api/v1/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get document content and metadata"""
    try:
        repo = get_document_repository()
        content = get_document_content(doc_id)
        metadata = repo.get_metadata(doc_id)
        
        return {
            "doc_id": doc_id,
            "content": content,
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading document: {str(e)}")


@app.get("/api/v1/documents/{doc_id}/metadata")
async def get_metadata(doc_id: str):
    """Get document metadata"""
    repo = get_document_repository()
    metadata = repo.get_metadata(doc_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Document metadata not found")
    return metadata


@app.put("/api/v1/documents/{doc_id}/metadata")
async def update_metadata(doc_id: str, request: UpdateMetadataRequest):
    """Update document metadata"""
    try:
        repo = get_document_repository()
        # Get existing metadata
        existing = repo.get_metadata(doc_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Update metadata
        repo.save_metadata(
            doc_id=doc_id,
            name=request.name or existing.get('name', ''),
            folder_id=existing.get('folder_id'),
            tags=request.tags if request.tags is not None else existing.get('tags', []),
            description=request.description if request.description is not None else existing.get('description', '')
        )
        
        return {
            "status": "success",
            "message": "Metadata updated"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating metadata: {str(e)}")


@app.get("/api/v1/documents/metadata/all")
async def get_all_metadata(folder_id: Optional[str] = Query(None, description="Filter by folder ID")):
    """Get metadata for all documents"""
    try:
        repo = get_document_repository()
        metadata_list = repo.get_all_metadata(folder_id)
        return {
            "documents": metadata_list,
            "count": len(metadata_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving metadata: {str(e)}")


@app.get("/api/v1/drive/mapping")
async def get_drive_mapping():
    """Get the current Drive file mapping from MongoDB"""
    try:
        repo = get_document_repository()
        mapping = repo.get_drive_mapping()
        return {
            "status": "success",
            "mapping": mapping
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving mapping: {str(e)}")


@app.post("/api/v1/drive/mapping/sync")
async def sync_drive_mapping(folder_id: Optional[str] = Query(None, description="Folder ID to sync (defaults to configured folder)")):
    """Sync Drive folder contents to MongoDB mapping"""
    try:
        mapping = sync_drive_folder_to_mapping(folder_id)
        return {
            "status": "success",
            "message": "Drive folder synced successfully",
            "mapping": mapping,
            "document_count": len(mapping.get("documents", []))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing Drive folder: {str(e)}")


@app.put("/api/v1/drive/mapping")
async def update_mapping(mapping: Dict[str, Any]):
    """Manually update the Drive file mapping"""
    try:
        repo = get_document_repository()
        updated_mapping = repo.update_drive_mapping(mapping)
        return {
            "status": "success",
            "message": "Mapping updated successfully",
            "mapping": updated_mapping
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating mapping: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Epimetheus API Service"}

