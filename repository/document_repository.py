"""
Document Repository

Handles MongoDB operations for document versions, metadata, and Drive mappings.
Also provides convenience methods that combine Drive and MongoDB operations.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.db_utils import get_mongodb_db, get_chroma_collection
from repository.drive_repository import get_drive_repository


class DocumentRepository:
    """Repository for document-related MongoDB operations"""
    
    def __init__(self):
        self.db = get_mongodb_db()
        self.collection = get_chroma_collection()
        self.drive_repo = get_drive_repository()
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

        # Drive file mapping collection (flat documents with folder_id)
        self.mapping_collection = self.db["drive_file_mapping"]
        self.mapping_collection.create_index([("doc_id", 1)], unique=True)
        self.mapping_collection.create_index([("folder_id", 1)])

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
    

    def get_drive_mapping(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all documents from the drive mapping collection, optionally filtered by folder_id"""
        if self.db is None:
            return []
        
        query = {}
        if folder_id:
            query["folder_id"] = folder_id
        
        documents = []
        for doc in self.mapping_collection.find(query):
            # Remove MongoDB _id field and convert datetime
            doc.pop("_id", None)
            if isinstance(doc.get("synced_at"), datetime):
                doc["synced_at"] = doc["synced_at"].isoformat()
            if isinstance(doc.get("updated_at"), datetime):
                doc["updated_at"] = doc["updated_at"].isoformat()
            documents.append(doc)
        
        return documents
    
    def upsert_drive_document(self, doc_id: str, name: str, folder_id: str, 
                             created_time: Optional[str] = None, 
                             modified_time: Optional[str] = None) -> Dict[str, Any]:
        """Insert or update a single document in the drive mapping collection"""
        if self.db is None:
            raise Exception("MongoDB connection not available")
        
        document = {
            "doc_id": doc_id,
            "name": name,
            "folder_id": folder_id,
            "created_time": created_time,
            "modified_time": modified_time,
            "updated_at": datetime.utcnow()
        }
        
        # Upsert the document
        self.mapping_collection.replace_one(
            {"doc_id": doc_id},
            document,
            upsert=True
        )
        
        return document
    
    # Convenience methods combining Drive and MongoDB operations
    
    def search_documents(self, query: str, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for documents by name or metadata"""
        if not folder_id:
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        
        documents = []
        
        # Search by name in Drive
        if folder_id:
            drive_results = self.drive_repo.search_documents_by_name(query, folder_id)
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
        """Sync Drive folder contents to MongoDB mapping (flat documents)"""
        if not folder_id:
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        
        if not folder_id:
            raise ValueError("GOOGLE_DRIVE_FOLDER_ID must be configured")
        
        # List documents from Drive
        drive_documents = self.drive_repo.list_documents_in_folder(folder_id)
        
        # Upsert each document individually into the mapping collection
        synced_docs = []
        for doc in drive_documents:
            document = self.upsert_drive_document(
                doc_id=doc['id'],
                name=doc['name'],
                folder_id=folder_id,
                created_time=doc.get('created_time'),
                modified_time=doc.get('modified_time')
            )
            synced_docs.append(document)
            
            # Update document metadata for each document
            existing_meta = self.get_metadata(doc['id'])
            if not existing_meta:
                self.save_metadata(
                    doc_id=doc['id'],
                    name=doc['name'],
                    folder_id=folder_id
                )
        
        # Return summary
        return {
            "folder_id": folder_id,
            "documents": synced_docs,
            "document_count": len(synced_docs),
            "synced_at": datetime.utcnow().isoformat()
        }
    
    def get_documents_from_mapping(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get documents from MongoDB mapping (flat collection) or Drive API"""
        if not folder_id:
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        
        if not folder_id:
            return []
        
        # First, try to get from MongoDB mapping (flat documents)
        mapping_docs = self.get_drive_mapping(folder_id=folder_id)
        
        if mapping_docs:
            # Convert to expected format (with 'id' field for compatibility)
            documents = []
            for doc in mapping_docs:
                documents.append({
                    "id": doc.get("doc_id"),
                    "name": doc.get("name"),
                    "created_time": doc.get("created_time"),
                    "modified_time": doc.get("modified_time")
                })
            return documents
        
        # Fallback to querying Drive API directly
        documents = self.drive_repo.list_documents_in_folder(folder_id)
        
        # Update mapping for future use
        if documents:
            for doc in documents:
                self.upsert_drive_document(
                    doc_id=doc['id'],
                    name=doc['name'],
                    folder_id=folder_id,
                    created_time=doc.get('created_time'),
                    modified_time=doc.get('modified_time')
                )
        
        return documents
    
    # Vector Database Operations
    
    def search_similar_documents(self, query_text: str, n_results: int = 3) -> Optional[Dict[str, Any]]:
        """Search for similar documents using vector search"""
        if not self.collection:
            return None
        
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            return results
        except Exception as e:
            print(f"Error searching similar documents: {e}")
            return None
    
    def delete_document_chunks(self, doc_id: str) -> bool:
        """Delete all chunks for a document from vector database"""
        if not self.collection:
            print("Warning: ChromaDB collection not available, skipping chunk deletion")
            return False
        
        try:
            self.collection.delete(where={"doc_id": doc_id})
            return True
        except Exception as e:
            print(f"Error deleting document chunks: {e}")
            return False
    
    def add_document_chunks(self, doc_id: str, chunks: List[str]) -> bool:
        """Add document chunks to vector database"""
        if not self.collection:
            print("Warning: ChromaDB collection not available, skipping chunk addition")
            return False
        
        if not chunks:
            return False
        
        try:
            self.collection.add(
                documents=chunks,
                ids=[f"{doc_id}_chunk_{i}" for i in range(len(chunks))],
                metadatas=[{"doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))]
            )
            return True
        except Exception as e:
            print(f"Error adding document chunks: {e}")
            return False


_document_repository = None


def get_document_repository() -> DocumentRepository:
    """Get or create the document repository singleton"""
    global _document_repository
    if _document_repository is None:
        _document_repository = DocumentRepository()
    return _document_repository
