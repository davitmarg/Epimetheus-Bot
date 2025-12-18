"""
Document Repository

Handles MongoDB operations for document versions, metadata, and Drive mappings.
Also provides convenience methods that combine Drive and MongoDB operations.
"""

import os
import uuid
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.db_utils import get_mongodb_db, get_chroma_collection, get_redis_client, REDIS_QUEUE_KEY
from utils.message_utils import extract_doc_id_from_chunk_id
from repository.drive_repository import get_drive_repository
from repository.llm_repository import get_llm_repository
from repository.slack_repository import get_slack_repository


class DocumentRepository:
    """Repository for document-related MongoDB operations"""
    
    def __init__(self):
        self.db = get_mongodb_db()
        self.collection = get_chroma_collection()
        self.drive_repo = get_drive_repository()
        self.llm_repo = get_llm_repository()
        self.slack_repo = get_slack_repository()
        self.redis_client = get_redis_client()
        # Assume folder_id is always there - get it from environment
        self.folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        if not self.folder_id:
            raise ValueError("GOOGLE_DRIVE_FOLDER_ID must be configured")
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
    
    def save_metadata(self, doc_id: str, name: str, folder_id: Optional[str] = None, tags: Optional[List[str]] = None, description: Optional[str] = None) -> Dict[str, Any]:
        """Save or update document metadata in MongoDB"""
        if self.db is None:
            raise Exception("MongoDB connection not available")
        
        metadata = {
            "doc_id": doc_id,
            "name": name,
            "folder_id": folder_id or self.folder_id,
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
        query["folder_id"] = folder_id or self.folder_id
        
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
    
    def upsert_drive_document(self, doc_id: str, name: str, folder_id: Optional[str] = None, created_time: Optional[str] = None, modified_time: Optional[str] = None) -> Dict[str, Any]:
        """Insert or update a single document in the drive mapping collection"""
        if self.db is None:
            raise Exception("MongoDB connection not available")
        
        document = {
            "doc_id": doc_id,
            "name": name,
            "folder_id": folder_id or self.folder_id,
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
        target_folder_id = folder_id or self.folder_id
        documents = []        
        drive_results = self.drive_repo.search_documents_by_name(query, target_folder_id)
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
        target_folder_id = folder_id or self.folder_id
        # List documents from Drive
        self.mapping_collection.delete_many({"folder_id": target_folder_id})
        drive_documents = self.drive_repo.list_documents_in_folder()
        
        # Upsert each document individually into the mapping collection
        synced_docs = []
        for doc in drive_documents:
            document = self.upsert_drive_document(
                doc_id=doc['id'],
                name=doc['name'],
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
                )
        
        # Return summary
        return {
            "folder_id": target_folder_id,
            "documents": synced_docs,
            "document_count": len(synced_docs),
            "synced_at": datetime.utcnow().isoformat()
        }
    
    def get_documents_from_mapping(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get documents from MongoDB mapping (flat collection) or Drive API"""
        target_folder_id = folder_id or self.folder_id
        # Always sync latest Drive state into MongoDB so mapping stays fresh
        try:
            self.sync_drive_folder_to_mapping(target_folder_id)
        except Exception as e:
            print(f"Drive Warning: Could not sync mapping before fetch: {e}")
        
        # First, try to get from MongoDB mapping (flat documents)
        mapping_docs = self.get_drive_mapping(target_folder_id)
        
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
        documents = self.drive_repo.list_documents_in_folder()
        
        # Update mapping for future use
        if documents:
            for doc in documents:
                self.upsert_drive_document(
                    doc_id=doc['id'],
                    name=doc['name'],
                    folder_id=target_folder_id,
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
    
    def determine_target_documents(self, messages: List[Dict[str, Any]], team_id: str) -> List[str]:
        """
        Determine which document(s) should receive these messages.
        
        This function can be customized to route messages to documents based on:
        - Content analysis (using vector search)
        - Channel/topic tags
        - Document metadata/tags
        - Default document selection
        
        Returns a list of document IDs.
        """
        # Strategy 1: Use vector search to find most relevant documents
        if messages:
            # Combine all message text
            combined_text = " ".join([msg.get('text', '') for msg in messages])
            
            if combined_text.strip():
                try:
                    # Search for similar content in vector DB
                    results = self.search_similar_documents(combined_text, n_results=3)
                    
                    if results and results.get('ids') and results['ids'][0]:
                        # Extract unique doc_ids from results
                        doc_ids = set()
                        for id_list in results['ids']:
                            for chunk_id in id_list:
                                # Extract doc_id from chunk_id (format: doc_id_chunk_N)
                                doc_id = extract_doc_id_from_chunk_id(chunk_id)
                                doc_ids.add(doc_id)
                        
                        if doc_ids:
                            return list(doc_ids)
                except Exception as e:
                    print(f"Warning: Vector search failed: {e}")
        
        # Strategy 2: Check for explicit document mentions or tags in messages
        # (This could be enhanced with NLP to detect document names)
        
        # Strategy 3: Use documents from Drive folder mapping
        try:
            # Get documents from mapping or list from folder
            docs = self.get_documents_from_mapping()
            if docs:
                # For now, return all documents (could be filtered by relevance)
                return [doc['id'] for doc in docs]
        except Exception as e:
            print(f"Drive Warning: Could not list documents in folder: {e}")
        
        # Last resort: create a default document
        try:
            default_doc = self.drive_repo.create_document(
                name=f"Team {team_id} Documentation",
                folder_id=self.folder_id,
                initial_content=""
            )
            return [default_doc['id']]
        except Exception as e:
            print(f"Drive Warning: Error creating default document: {e}")
        
        return []
    
    def chunk_document(self, content: str, chunk_size: int = 1000) -> List[str]:
        """Split document into chunks for vector storage"""
        chunks = []
        words = content.split()
        current_chunk = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 for space
            if current_size + word_size > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_size = len(word)
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def update_vector_db(self, doc_id: str, content: str):
        """Update vector database with document chunks"""
        chunks = self.chunk_document(content)
        
        # Delete old chunks for this document
        self.delete_document_chunks(doc_id)
        
        # Add new chunks
        if chunks:
            self.add_document_chunks(doc_id, chunks)
    
    def generate_document_update(self, old_content: str, new_messages: List[Dict[str, Any]]) -> str:
        """Use LLM repository to generate updated document content"""
        try:
            return self.llm_repo.generate_document_update(
                old_content=old_content,
                new_messages=new_messages,
                temperature=0.3,
                max_tokens=4000
            )
        except Exception as e:
            raise Exception(f"Error generating document update: {str(e)}")
    
    def generate_change_summary(self, old_content: str, new_content: str, new_messages: List[Dict[str, Any]], doc_id: Optional[str] = None) -> str:
        """Use LLM repository to generate a concise summary of document changes"""
        try:
            return self.llm_repo.generate_change_summary(
                old_content=old_content,
                new_content=new_content,
                new_messages=new_messages,
                doc_id=doc_id,
                temperature=0.5,
                max_tokens=200
            )
        except Exception as e:
            print(f"Warning: Error generating change summary: {str(e)}")
            return "Document updated successfully."
    
    def chunk_messages(self, messages: List[Dict[str, Any]], chunk_size: int = None) -> List[List[Dict[str, Any]]]:
        """
        Chunk messages into groups of last N messages.
        
        Args:
            messages: List of message dictionaries
            chunk_size: Number of messages per chunk (defaults to MESSAGE_CHUNK_SIZE env var or 10)
            
        Returns:
            List of message chunks (each chunk is a list of messages)
        """
        if chunk_size is None:
            chunk_size = int(os.environ.get("MESSAGE_CHUNK_SIZE", "10"))
        
        if not messages:
            return []
        
        # Filter out bot messages
        user_messages = [msg for msg in messages if not msg.get("bot_id")]
        
        if not user_messages:
            return []
        
        # Sort messages by timestamp (oldest first)
        sorted_messages = sorted(user_messages, key=lambda x: float(x.get("ts", 0)))
        
        # Create chunks of last N messages
        chunks = []
        for i in range(len(sorted_messages)):
            chunk = sorted_messages[max(0, i - chunk_size + 1):i + 1]
            if len(chunk) >= 2:  # Only include chunks with at least 2 messages
                chunks.append(chunk)
        
        # Return the most recent chunk if we have messages
        if sorted_messages:
            recent_chunk = sorted_messages[-chunk_size:] if len(sorted_messages) >= chunk_size else sorted_messages
            return [recent_chunk]
        
        return []
    
    def extract_knowledge_from_chunk(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract knowledge from a chunk of messages using LLM.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Dictionary with extracted knowledge and metadata
        """
        if not messages:
            return {
                "knowledge": "",
                "has_new_information": False,
                "relevance_score": 0.0
            }
        
        # Combine message texts
        message_texts = []
        for msg in messages:
            text = msg.get("text", "")
            user = msg.get("user", "unknown")
            timestamp = msg.get("ts", "")
            message_texts.append(f"[{timestamp}] {user}: {text}")
        
        combined_text = "\n".join(message_texts)
        
        # Use LLM repository to extract knowledge
        try:
            knowledge = self.llm_repo.extract_knowledge(
                conversation_text=combined_text,
                temperature=0.3,
                max_tokens=500
            )
            
            # Check if there's new information
            has_new_information = knowledge.upper() != "NO_NEW_INFORMATION" and len(knowledge) > 20
            
            # Calculate relevance score based on knowledge length and content
            relevance_score = 0.0
            if has_new_information:
                # Simple heuristic: longer, more detailed knowledge = higher relevance
                relevance_score = min(1.0, len(knowledge) / 500.0)
            
            return {
                "knowledge": knowledge,
                "has_new_information": has_new_information,
                "relevance_score": relevance_score,
                "message_count": len(messages)
            }
            
        except Exception as e:
            print(f"Error extracting knowledge: {e}")
            return {
                "knowledge": "",
                "has_new_information": False,
                "relevance_score": 0.0,
                "error": str(e)
            }
    
    def determine_if_document_needs_update(
        self,
        knowledge: str,
        messages: List[Dict[str, Any]],
        team_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Determine if a document needs updating based on extracted knowledge.
        Uses RAG to find relevant documents.
        
        Args:
            knowledge: Extracted knowledge string
            messages: Original messages that generated the knowledge
            team_id: Slack team ID
            
        Returns:
            Dictionary with doc_id and confidence, or None if no update needed
        """
        knowledge_extraction_threshold = float(os.environ.get("KNOWLEDGE_EXTRACTION_THRESHOLD", "0.7"))
        
        if not knowledge or len(knowledge.strip()) < 20:
            return None
        
        try:
            # Use vector search to find relevant documents
            search_results = self.search_similar_documents(knowledge, n_results=3)
            
            if not search_results or not search_results.get('ids') or not search_results['ids'][0]:
                # No relevant documents found, but knowledge exists
                # Could create a new document or return None
                return None
            
            # Get the most relevant document
            chunk_ids = search_results['ids'][0]
            distances_list = search_results.get('distances', [[]])[0]
            
            if not chunk_ids or not distances_list:
                return None
            
            # Extract doc_id from first chunk
            first_chunk_id = chunk_ids[0]
            doc_id = extract_doc_id_from_chunk_id(first_chunk_id)
            distance = distances_list[0] if len(distances_list) > 0 else 1.0
            
            # Check if relevance is high enough (lower distance = more relevant)
            relevance_threshold = 1.0 - knowledge_extraction_threshold  # Convert threshold to distance
            
            if distance < relevance_threshold:
                return {
                    "doc_id": doc_id,
                    "confidence": 1.0 - distance,  # Convert distance to confidence
                    "distance": distance
                }
            
            return None
            
        except Exception as e:
            print(f"Error determining document update need: {e}")
            return None
    
    def process_document_update(self, doc_id: str, messages: List[Dict[str, Any]], trigger_type: str = "agent_command") -> Dict[str, Any]:
        """
        Process document update immediately with the given messages
        
        Returns:
            Dict with 'success' (bool), 'doc_id', 'doc_name', 'message_count', 'version_id', 'change_summary', 'error' (optional)
        """
        result = {
            "success": False,
            "doc_id": doc_id,
            "doc_name": None,
            "message_count": len(messages),
            "version_id": None,
            "change_summary": None,
            "error": None
        }
        
        if not messages:
            result["error"] = "No messages provided"
            print(f"No messages provided for document {doc_id}")
            return result
        
        # Get document name from metadata
        try:
            metadata = self.get_metadata(doc_id)
            result["doc_name"] = metadata.get("name", "Unknown Document") if metadata else "Unknown Document"
        except Exception as e:
            result["doc_name"] = "Unknown Document"
            print(f"Warning: Could not get document metadata: {e}")
        
        # Get current document content
        try:
            old_content = self.drive_repo.get_document_content(doc_id)
        except Exception as e:
            result["error"] = f"Error reading document: {str(e)}"
            print(f"Error reading document {doc_id}: {e}")
            return result
        
        # Generate new content
        try:
            new_content = self.generate_document_update(old_content, messages)
        except Exception as e:
            result["error"] = f"Error generating update: {str(e)}"
            print(f"Error generating update for {doc_id}: {e}")
            return result
        
        # Generate change summary
        try:
            result["change_summary"] = self.generate_change_summary(old_content, new_content, messages, doc_id)
        except Exception as e:
            print(f"Warning: Error generating change summary: {e}")
            result["change_summary"] = "Document updated successfully."
        
        # Calculate metadata
        char_count = sum(len(msg.get('text', '')) for msg in messages)
        
        # Save version before update
        version_metadata = {
            "char_count": char_count,
            "message_count": len(messages),
            "trigger_type": trigger_type
        }
        try:
            version_id = self.save_version(doc_id, old_content, version_metadata)
            result["version_id"] = version_id
        except Exception as e:
            result["error"] = f"Error saving version: {str(e)}"
            print(f"Error saving version for {doc_id}: {e}")
            return result
        
        try:
            self.drive_repo.update_document_content_partial(doc_id, old_content, new_content)
        except Exception as e:
            result["error"] = f"Error updating Google Doc: {str(e)}"
            print(f"Error updating Google Doc {doc_id}: {e}")
            return result
        
        # Update vector database
        try:
            self.update_vector_db(doc_id, new_content)
        except Exception as e:
            # Don't fail the update if vector DB fails, just log it
            print(f"Warning: Error updating vector DB for {doc_id}: {e}")
        
        result["success"] = True
        print(f"✓ Successfully updated document {doc_id} (version {version_id}) with {len(messages)} message(s)")
        return result
    
    def ingest_messages(self, payload: Dict[str, Any]):
        """
        Process messages from Redis queue as a log.
        
        Works as a log that:
        1. Chunks messages
        2. Extracts knowledge from chunks
        3. Checks if document needs update
        4. If update needed: processes update
        5. If not needed: flushes and continues
        """
        team_id = payload.get('team_id')
        threads = payload.get('threads', [])
        channel = payload.get('channel')
        thread_ts = payload.get('thread_ts')
        
        if not threads:
            return
        
        # Collect all messages from all threads
        all_messages = []
        for thread_batch in threads:
            all_messages.extend(thread_batch.get('messages', []))
        
        if not all_messages:
            print(f"⏭️  No messages to process, flushing")
            return
        
        # Chunk messages
        message_chunks = self.chunk_messages(all_messages)
        
        if not message_chunks:
            print(f"⏭️  No valid chunks from {len(all_messages)} messages, flushing")
            return
        
        # Process the most recent chunk
        latest_chunk = message_chunks[-1]
        
        # Extract knowledge from the chunk
        knowledge_result = self.extract_knowledge_from_chunk(latest_chunk)
        
        if not knowledge_result.get("has_new_information"):
            print(f"⏭️  No new knowledge extracted from {len(latest_chunk)} messages, flushing")
            return
        
        knowledge = knowledge_result.get("knowledge", "")
        print(f"📝 Extracted knowledge from {len(latest_chunk)} messages: {knowledge[:100]}...")
        
        # Determine if a document needs updating
        update_decision = self.determine_if_document_needs_update(
            knowledge=knowledge,
            messages=latest_chunk,
            team_id=team_id
        )
        
        if not update_decision:
            print(f"⏭️  No document update needed, flushing")
            return
        
        # Document needs update - process it
        doc_id = update_decision["doc_id"]
        confidence = update_decision["confidence"]
        
        print(f"📄 Document {doc_id} needs update (confidence: {confidence:.2f})")
        
        # Process the document update
        result = self.process_document_update(
            doc_id=doc_id,
            messages=latest_chunk,
            trigger_type="redis_queue"
        )
        
        # Send Slack notification if channel and thread_ts are available
        if channel and thread_ts:
            self.slack_repo.send_document_update_notification(
                channel=channel,
                thread_ts=thread_ts,
                doc_id=result["doc_id"],
                doc_name=result["doc_name"] or "Unknown Document",
                message_count=result["message_count"],
                success=result["success"],
                error_message=result.get("error"),
                change_summary=result.get("change_summary")
            )
        
        if result["success"]:
            print(f"✓ Successfully updated document {doc_id} based on queue log")
        else:
            print(f"✗ Failed to update document {doc_id}: {result.get('error')}")
    
    def consume_from_redis(self):
        """
        Consume messages from Redis queue as a log.
        
        Continuously processes messages from queue, checking chunks for knowledge extraction
        and only updating documents when needed.
        """
        print(f"Starting Redis consumer on queue: {REDIS_QUEUE_KEY}")
        print(f"Update processing uses BOTH direct calls and Redis queue consumption.")
        print(f"Waiting for messages from Redis queue...")
        
        # Verify Redis connection and queue status
        try:
            self.redis_client.ping()
            queue_length = self.redis_client.llen(REDIS_QUEUE_KEY)
            print(f"✓ Redis connected. Queue '{REDIS_QUEUE_KEY}' length: {queue_length}")
            if queue_length > 0:
                print(f"  Found {queue_length} message(s) already in queue")
        except Exception as e:
            print(f"✗ Redis connection check failed: {e}")
        
        last_heartbeat = time.time()
        heartbeat_interval = 30  # Print heartbeat every 30 seconds
        
        while True:
            try:
                # Blocking pop from queue (wait up to 1 second)
                # blpop returns (key, value) tuple or None if timeout
                result = self.redis_client.blpop(REDIS_QUEUE_KEY, timeout=1)
                if result:
                    # result is a tuple: (key, value)
                    queue_key, payload_json = result
                    
                    try:
                        payload = json.loads(payload_json)
                        team_id = payload.get('team_id', 'unknown')
                        thread_count = len(payload.get('threads', []))
                        
                        total_messages = sum(len(t.get('messages', [])) for t in payload.get('threads', []))
                        print(f"✓ Received message(s) for team {team_id}: {thread_count} thread(s), {total_messages} message(s)")
                        self.ingest_messages(payload)
                        print(f"✓ Successfully processed message(s) for team {team_id}")
                        
                    except json.JSONDecodeError as e:
                        print(f"✗ Error decoding JSON payload: {e}")
                        print(f"  Raw payload: {payload_json[:200]}...")
                        continue
                    except Exception as e:
                        print(f"✗ Error processing batch: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                else:
                    # No message available, continue polling
                    # Print periodic heartbeat to show service is still running
                    current_time = time.time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        queue_length = self.redis_client.llen(REDIS_QUEUE_KEY)
                        print(f"⏳ Waiting for messages on queue: {REDIS_QUEUE_KEY} (current length: {queue_length})")
                        last_heartbeat = current_time
                    time.sleep(0.1)
                    
            except Exception as e:
                error_str = str(e).lower()
                if "connection" in error_str or "connectionerror" in error_str:
                    print(f"✗ Redis connection error: {e}. Retrying in 5 seconds...")
                    time.sleep(5)
                    # Try to reconnect
                    try:
                        self.redis_client.ping()
                        print(f"✓ Redis connection restored")
                    except:
                        pass
                else:
                    print(f"✗ Unexpected error in consume loop: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(1)


_document_repository = None


def get_document_repository() -> DocumentRepository:
    """Get or create the document repository singleton"""
    global _document_repository
    if _document_repository is None:
        _document_repository = DocumentRepository()
    return _document_repository
