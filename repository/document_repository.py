"""
Document Repository

Handles MongoDB operations for document versions, metadata, and Drive mappings.
Also provides convenience methods that combine Drive and MongoDB operations.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.db_utils import get_mongodb_db
from repository.drive_repository import (
    list_documents_in_folder,
    search_documents_by_name,
)


class DocumentRepository:
    """Repository for document-related MongoDB operations"""
    
    def __init__(self):
        self.db = get_mongodb_db()
        if self.db is not None:
            self._init_collections()
    
    def _init_collections(self):
        """Initialize MongoDB collections and indexes"""

        # Document versions collection
        self.versions_collection = self.db["document_versions"]
        self.versions_collection.create_index([("doc_id", 1), ("created_at", -1)])

        # Document metadata collection
        self.metadata_collection = self.db["document_metadata"]
        self.metadata_collection.create_index([("doc_id", 1)])
        self.metadata_collection.create_index([("folder_id", 1)])

        # Drive file mapping collection
        self.mapping_collection = self.db["drive_file_mapping"]
        self.mapping_collection.create_index([("type", 1)])

    def save_version(self, doc_id: str, content: str, version_metadata: Dict[str, Any]) -> str:
        """Save a document version to MongoDB"""
        if self.db is None:
            raise Exception("MongoDB connection not available")

        version_id = str(uuid.uuid4())
        version_data = {
            "version_id": version_id,
            "doc_id": doc_id,
            "content": content,
            "created_at": datetime.utcnow(),
            "metadata": version_metadata
        }
        
        try:
            self.versions_collection.insert_one(version_data)
            return version_id
        except Exception as e:
            raise Exception(f"Error saving version to MongoDB: {str(e)}")
    
    def load_version(self, doc_id: str, version_id: str) -> Optional[Dict[str, Any]]:
        """Load a document version from MongoDB"""
        if self.db is None:
            return None
        
        try:
            version_doc = self.versions_collection.find_one({
                "doc_id": doc_id,
                "version_id": version_id
            })
            
            if version_doc:
                # Convert ObjectId to string and datetime to ISO string for JSON serialization
                version_doc["_id"] = str(version_doc["_id"])
                if isinstance(version_doc.get("created_at"), datetime):
                    version_doc["created_at"] = version_doc["created_at"].isoformat()
                return version_doc
            return None
        except Exception as e:
            print(f"Error loading version from MongoDB: {e}")
            return None
    
    def list_versions(self, doc_id: str) -> List[Dict[str, Any]]:
        """List all versions for a document from MongoDB"""
        if self.db is None:
            return []
        
        try:
            versions_cursor = self.versions_collection.find(
                {"doc_id": doc_id},
                {"version_id": 1, "created_at": 1, "metadata": 1}
            ).sort("created_at", -1)
            
            versions = []
            for version_doc in versions_cursor:
                version_data = {
                    "version_id": version_doc.get("version_id"),
                    "created_at": version_doc.get("created_at").isoformat() if isinstance(version_doc.get("created_at"), datetime) else version_doc.get("created_at"),
                    "metadata": version_doc.get("metadata", {})
                }
                versions.append(version_data)
            
            return versions
        except Exception as e:
            print(f"Error listing versions from MongoDB: {e}")
            return []
    
    # Document Metadata
    
    def save_metadata(self, doc_id: str, name: str, folder_id: Optional[str] = None, 
                     tags: Optional[List[str]] = None, description: Optional[str] = None) -> Dict[str, Any]:
        """Save or update document metadata in MongoDB"""
        if self.db is None:
            raise Exception("MongoDB connection not available")
        
        metadata = {
            "doc_id": doc_id,
            "name": name,
            "folder_id": folder_id,
            "tags": tags or [],
            "description": description or "",
            "updated_at": datetime.utcnow()
        }
        
        # Check if document already exists
        existing = self.metadata_collection.find_one({"doc_id": doc_id})
        
        if existing:
            # Update existing metadata
            metadata["created_at"] = existing.get("created_at", datetime.utcnow())
            self.metadata_collection.update_one(
                {"doc_id": doc_id},
                {"$set": metadata}
            )
        else:
            # Insert new metadata
            metadata["created_at"] = datetime.utcnow()
            self.metadata_collection.insert_one(metadata)
        
        return metadata
    
    def get_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata from MongoDB"""
        if self.db is None:
            return None
        
        metadata = self.metadata_collection.find_one({"doc_id": doc_id})
        
        if metadata:
            # Convert ObjectId and datetime for JSON serialization
            metadata["_id"] = str(metadata["_id"])
            if isinstance(metadata.get("created_at"), datetime):
                metadata["created_at"] = metadata["created_at"].isoformat()
            if isinstance(metadata.get("updated_at"), datetime):
                metadata["updated_at"] = metadata["updated_at"].isoformat()
        
        return metadata
    
    def get_all_metadata(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get metadata for all documents, optionally filtered by folder"""
        if self.db is None:
            return []
        
        query = {}
        if folder_id:
            query["folder_id"] = folder_id
        
        results = self.metadata_collection.find(query)
        
        documents = []
        for meta in results:
            meta["_id"] = str(meta["_id"])
            if isinstance(meta.get("created_at"), datetime):
                meta["created_at"] = meta["created_at"].isoformat()
            if isinstance(meta.get("updated_at"), datetime):
                meta["updated_at"] = meta["updated_at"].isoformat()
            documents.append(meta)
        
        return documents
    
    def search_metadata(self, query: str) -> List[Dict[str, Any]]:
        """Search document metadata by name, tags, or description"""
        if self.db is None:
            return []
        
        try:
            metadata_results = self.metadata_collection.find({
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"tags": {"$in": [query]}},
                    {"description": {"$regex": query, "$options": "i"}}
                ]
            })
            
            documents = []
            for meta in metadata_results:
                meta["_id"] = str(meta["_id"])
                if isinstance(meta.get("created_at"), datetime):
                    meta["created_at"] = meta["created_at"].isoformat()
                if isinstance(meta.get("updated_at"), datetime):
                    meta["updated_at"] = meta["updated_at"].isoformat()
                documents.append(meta)
            
            return documents
        except Exception as e:
            print(f"Error searching metadata: {e}")
            return []
    
    # Drive File Mapping
    
    def get_drive_mapping(self) -> Dict[str, Any]:
        """Get the Drive file mapping from MongoDB"""
        if self.db is None:
            return {}
        
        mapping = self.mapping_collection.find_one({"type": "drive_mapping"})
        
        if mapping:
            # Remove MongoDB _id field
            mapping.pop("_id", None)
            mapping.pop("type", None)
        else:
            mapping = {}
        
        return mapping
    
    def update_drive_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Update the Drive file mapping in MongoDB"""
        if self.db is None:
            raise Exception("MongoDB connection not available")
        
        # Ensure type field is set
        mapping["type"] = "drive_mapping"
        mapping["updated_at"] = datetime.utcnow()
        
        # Upsert the mapping
        self.mapping_collection.replace_one(
            {"type": "drive_mapping"},
            mapping,
            upsert=True
        )
        
        return mapping
    
    # Convenience methods combining Drive and MongoDB operations
    
    def search_documents(self, query: str, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for documents by name or metadata"""
        if not folder_id:
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        
        documents = []
        
        # Search by name in Drive
        if folder_id:
            drive_results = search_documents_by_name(query, folder_id)
            documents.extend(drive_results)
        
        # Search in MongoDB metadata
        metadata_results = self.search_metadata(query)
        
        for meta in metadata_results:
            # Check if already in results
            if not any(doc['id'] == meta['doc_id'] for doc in documents):
                documents.append({
                    "id": meta['doc_id'],
                    "name": meta.get('name', 'Unknown'),
                    "created_time": meta.get('created_at'),
                    "modified_time": meta.get('updated_at'),
                    "match_type": "metadata"
                })
        
        return documents
    
    def sync_drive_folder_to_mapping(self, folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Sync Drive folder contents to MongoDB mapping"""
        if not folder_id:
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        
        if not folder_id:
            raise ValueError("GOOGLE_DRIVE_FOLDER_ID must be configured")
        
        # List documents from Drive
        documents = list_documents_in_folder(folder_id)
        
        # Build mapping structure
        mapping = {
            "folder_id": folder_id,
            "documents": documents,
            "synced_at": datetime.utcnow().isoformat()
        }
        
        # Update document metadata for each document
        for doc in documents:
            existing_meta = self.get_metadata(doc['id'])
            if not existing_meta:
                self.save_metadata(
                    doc_id=doc['id'],
                    name=doc['name'],
                    folder_id=folder_id
                )
        
        # Save mapping to MongoDB
        self.update_drive_mapping(mapping)
        return mapping
    
    def get_documents_from_mapping(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get documents from MongoDB mapping or Drive API"""
        if not folder_id:
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        
        if not folder_id:
            return []
        
        # First, try to get from MongoDB mapping
        mapping = self.get_drive_mapping()
        
        if mapping and mapping.get("folder_id") == folder_id and mapping.get("documents"):
            return mapping["documents"]
        
        # Fallback to querying Drive API directly
        documents = list_documents_in_folder(folder_id)
        
        # Update mapping for future use
        if documents:
            mapping = {
                "folder_id": folder_id,
                "documents": documents,
                "synced_at": datetime.utcnow().isoformat()
            }
            self.update_drive_mapping(mapping)
        
        return documents


_document_repository = None


def get_document_repository() -> DocumentRepository:
    """Get or create the document repository singleton"""
    global _document_repository
    if _document_repository is None:
        _document_repository = DocumentRepository()
    return _document_repository


# Convenience functions for backward compatibility
def search_documents(query: str, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search for documents by name or metadata"""
    repo = get_document_repository()
    return repo.search_documents(query, folder_id)


def sync_drive_folder_to_mapping(folder_id: Optional[str] = None) -> Dict[str, Any]:
    """Sync Drive folder contents to MongoDB mapping"""
    repo = get_document_repository()
    return repo.sync_drive_folder_to_mapping(folder_id)


def get_documents_from_mapping(folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get documents from MongoDB mapping or Drive API"""
    repo = get_document_repository()
    return repo.get_documents_from_mapping(folder_id)
