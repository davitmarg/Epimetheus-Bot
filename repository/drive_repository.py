"""
Google Drive Repository

Handles all Google Drive API operations for documents.
"""

import os
from typing import Dict, Any, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class DriveRepository:
    """Repository for Google Drive and Docs API operations"""
    
    def __init__(self):
        self.credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH")
        self.default_folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        self._docs_service = None
        self._drive_service = None
    
    def _get_google_docs_service(self):
        """Initialize and return Google Docs API service"""
        if self._docs_service is None:
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                raise ValueError("Google credentials file not found")
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/documents',
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/drive.file'
                ]
            )
            self._docs_service = build('docs', 'v1', credentials=credentials)
        return self._docs_service
    
    def _get_google_drive_service(self):
        """Initialize and return Google Drive API service"""
        if self._drive_service is None:
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                raise ValueError("Google credentials file not found")
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/documents',
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/drive.file'
                ]
            )
            self._drive_service = build('drive', 'v3', credentials=credentials)
        return self._drive_service


    def list_documents_in_folder(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all Google Docs in a Drive folder"""
        if not folder_id:
            folder_id = self.default_folder_id
        
        if not folder_id:
            return []
        
        try:
            drive_service = self._get_google_drive_service()
            
            # Query for Google Docs in the folder
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            
            results = drive_service.files().list(
                q=query,
                fields="files(id, name, createdTime, modifiedTime, mimeType)",
                orderBy="modifiedTime desc"
            ).execute()
            
            documents = []
            for file in results.get('files', []):
                documents.append({
                    "id": file['id'],
                    "name": file['name'],
                    "created_time": file.get('createdTime'),
                    "modified_time": file.get('modifiedTime')
                })
            
            return documents
        except HttpError as e:
            raise Exception(f"Error listing documents in folder: {str(e)}")
    
    def search_documents_by_name(self, query: str, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for documents by name in a Drive folder"""
        if not folder_id:
            folder_id = self.default_folder_id
        
        if not folder_id:
            return []
        
        try:
            drive_service = self._get_google_drive_service()
            
            name_query = f"'{folder_id}' in parents and name contains '{query}' and mimeType='application/vnd.google-apps.document' and trashed=false"
            
            results = drive_service.files().list(
                q=name_query,
                fields="files(id, name, createdTime, modifiedTime)",
                orderBy="modifiedTime desc"
            ).execute()
            
            documents = []
            for file in results.get('files', []):
                documents.append({
                    "id": file['id'],
                    "name": file['name'],
                    "created_time": file.get('createdTime'),
                    "modified_time": file.get('modifiedTime'),
                    "match_type": "name"
                })
            
            return documents
        except HttpError as e:
            raise Exception(f"Error searching documents: {str(e)}")
    
    def get_document_content(self, doc_id: str) -> str:
        """Retrieve current content from Google Doc"""
        try:
            service = self._get_google_docs_service()
            doc = service.documents().get(documentId=doc_id).execute()
            content = doc.get('body', {}).get('content', [])
            text_parts = []
            
            def extract_text(element):
                if 'paragraph' in element:
                    for para_elem in element['paragraph'].get('elements', []):
                        if 'textRun' in para_elem:
                            text_parts.append(para_elem['textRun'].get('content', ''))
                elif 'table' in element:
                    for row in element['table'].get('tableRows', []):
                        for cell in row.get('tableCells', []):
                            for cell_elem in cell.get('content', []):
                                extract_text(cell_elem)
            
            for element in content:
                extract_text(element)
            
            return ''.join(text_parts)
        except HttpError as e:
            raise Exception(f"Error reading Google Doc: {str(e)}")
    
    def update_document_content(self, doc_id: str, new_content: str):
        """Update Google Doc with new content"""
        try:
            service = self._get_google_docs_service()
            
            # Get current document to find end index
            doc = service.documents().get(documentId=doc_id).execute()
            end_index = doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)
            
            # Clear existing content (except first element which is required)
            if end_index > 1:
                requests = [{
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': end_index - 1
                        }
                    }
                }]
                service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()
            
            # Insert new content
            requests = [{
                'insertText': {
                    'location': {'index': 1},
                    'text': new_content
                }
            }]
            service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
        except HttpError as e:
            raise Exception(f"Error updating Google Doc: {str(e)}")
    
    def create_document(self, name: str, folder_id: Optional[str] = None, initial_content: str = "") -> Dict[str, Any]:
        """Create a new Google Doc in the specified folder"""
        if not folder_id:
            folder_id = self.default_folder_id
        
        try:
            docs_service = self._get_google_docs_service()
            drive_service = self._get_google_drive_service()
            
            # Create the document
            doc = docs_service.documents().create(body={'title': name}).execute()
            doc_id = doc.get('documentId')
            
            # If initial content provided, add it
            if initial_content:
                self.update_document_content(doc_id, initial_content)
            
            # Move to folder if folder_id specified
            if folder_id:
                # Get the current parents
                file = drive_service.files().get(fileId=doc_id, fields='parents').execute()
                previous_parents = ",".join(file.get('parents'))
                
                # Move to new folder
                drive_service.files().update(
                    fileId=doc_id,
                    addParents=folder_id,
                    removeParents=previous_parents,
                    fields='id, parents'
                ).execute()
            
            return {
                "id": doc_id,
                "name": name,
                "folder_id": folder_id
            }
        except HttpError as e:
            raise Exception(f"Error creating document: {str(e)}")


_drive_repository = None


def get_drive_repository() -> DriveRepository:
    """Get or create the drive repository singleton"""
    global _drive_repository
    if _drive_repository is None:
        _drive_repository = DriveRepository()
    return _drive_repository


# Convenience functions for backward compatibility
def list_documents_in_folder(folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all Google Docs in a Drive folder"""
    repo = get_drive_repository()
    return repo.list_documents_in_folder(folder_id)


def search_documents_by_name(query: str, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search for documents by name in a Drive folder"""
    repo = get_drive_repository()
    return repo.search_documents_by_name(query, folder_id)


def get_document_content(doc_id: str) -> str:
    """Retrieve current content from Google Doc"""
    repo = get_drive_repository()
    return repo.get_document_content(doc_id)


def update_document_content(doc_id: str, new_content: str):
    """Update Google Doc with new content"""
    repo = get_drive_repository()
    return repo.update_document_content(doc_id, new_content)


def create_document(name: str, folder_id: Optional[str] = None, initial_content: str = "") -> Dict[str, Any]:
    """Create a new Google Doc in the specified folder"""
    repo = get_drive_repository()
    return repo.create_document(name, folder_id, initial_content)


# Legacy function names for backward compatibility with tests
def _get_google_docs_service():
    """Legacy function - use DriveRepository._get_google_docs_service() instead"""
    repo = get_drive_repository()
    return repo._get_google_docs_service()


def _get_google_drive_service():
    """Legacy function - use DriveRepository._get_google_drive_service() instead"""
    repo = get_drive_repository()
    return repo._get_google_drive_service()

