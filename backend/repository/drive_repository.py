"""
Google Drive Repository

Handles all Google Drive API operations for documents.
"""

import os
import re
import difflib
from typing import Dict, Any, List, Optional, Tuple
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils.logger import get_logger

logger = get_logger(__name__)


class DriveRepository:
    """
    Repository for Google Drive and Docs API operations.
    
    Document Update Flow:
    1. AI Agent generates markdown content (with headings, bold, italic, lists, etc.)
    2. convert_markdown_to_google_docs_format() converts markdown to Google Docs API format requests
    3. update_document_content() inserts plain text and applies formatting requests
    4. Document is updated with proper Google Docs formatting
    
    All document updates support markdown formatting by default.
    """
    
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


    def list_documents_in_folder(self) -> List[Dict[str, Any]]:
        """List all Google Docs in a Drive folder"""
        folder_id = self.default_folder_id
        
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
    
    def _compute_text_diff(self, old_text: str, new_text: str, min_chunk_size: int = 10) -> List[Dict[str, Any]]:
        """
        Compute differences between old and new text using difflib.
        Returns list of operations optimized for Google Docs API.
        Uses replaceAllText for replacements (preserves formatting) and handles insertions/deletions.
        
        Args:
            old_text: Original text content
            new_text: New text content
            min_chunk_size: Minimum size of text chunks to process (avoids too many small updates)
        
        Returns:
            List of operations: {'type': 'replace'|'insert'|'delete', 'old_text': str, 'new_text': str, 'position': int}
        """
        operations = []
        
        # Use SequenceMatcher to find matching blocks
        matcher = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            old_segment = old_text[i1:i2]
            new_segment = new_text[j1:j2]
            
            if tag == 'replace':
                # Text was replaced - use replaceAllText (preserves formatting)
                if len(old_segment.strip()) >= min_chunk_size:
                    operations.append({
                        'type': 'replace',
                        'old_text': old_segment,
                        'new_text': new_segment
                    })
            elif tag == 'delete':
                # Text was deleted
                if len(old_segment.strip()) >= min_chunk_size:
                    operations.append({
                        'type': 'delete',
                        'old_text': old_segment
                    })
            elif tag == 'insert':
                # Text was inserted - need insertion point
                if len(new_segment.strip()) >= min_chunk_size:
                    operations.append({
                        'type': 'insert',
                        'new_text': new_segment,
                        'position': i1  # Insert after this position in old text
                    })
            # 'equal' tag means no change, skip it
        
        return operations
    
    def _apply_partial_updates(self, doc_id: str, old_text: str, new_text: str) -> None:
        """
        Apply partial updates to Google Doc while preserving formatting.
        Uses replaceAllText for replacements (which preserves formatting automatically)
        and handles insertions/deletions intelligently.
        """
        try:
            service = self._get_google_docs_service()
            
            # Get current document content to verify it matches old_text
            current_text = self.get_document_content(doc_id)
            
            # If documents are identical, no update needed
            if old_text == new_text:
                return
            
            # If old_text doesn't match current document, fall back to full replacement
            # (This handles cases where document was edited outside our system)
            if old_text != current_text:
                logger.warning("Document content mismatch. Using full replacement.")
                self.update_document_content(doc_id, new_text)
                return
            
            # Compute differences
            diff_operations = self._compute_text_diff(old_text, new_text, min_chunk_size=5)
            
            if not diff_operations:
                # If no meaningful differences found but texts differ, use full replacement
                if old_text != new_text:
                    logger.warning("Could not compute meaningful diff. Using full replacement.")
                    self.update_document_content(doc_id, new_text)
                return
            
            # Build batch update requests
            requests = []
            
            # Process replacements first (using replaceAllText - preserves formatting)
            replace_ops = [op for op in diff_operations if op['type'] == 'replace']
            for op in replace_ops:
                # Escape special characters for replaceAllText
                old_text_escaped = op['old_text'].replace('\\', '\\\\').replace('$', '\\$')
                requests.append({
                    'replaceAllText': {
                        'containsText': {
                            'text': old_text_escaped,
                            'matchCase': False
                        },
                        'replaceText': op['new_text']
                    }
                })
            
            # Process deletions (find and delete text)
            delete_ops = [op for op in diff_operations if op['type'] == 'delete']
            for op in delete_ops:
                # Use replaceAllText with empty replacement (effectively deletes)
                old_text_escaped = op['old_text'].replace('\\', '\\\\').replace('$', '\\$')
                requests.append({
                    'replaceAllText': {
                        'containsText': {
                            'text': old_text_escaped,
                            'matchCase': False
                        },
                        'replaceText': ''
                    }
                })
            
            # Process insertions - insert at appropriate positions
            # Strategy: For insertions, we'll insert at the end of the document
            # This is simpler and safer than trying to find exact positions
            # The LLM-generated content should be structured such that insertions
            # are typically additions at the end anyway
            insert_ops = [op for op in diff_operations if op['type'] == 'insert']
            
            if insert_ops:
                # Get document structure to find end index
                doc = service.documents().get(documentId=doc_id).execute()
                end_index = doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)
                
                # Sort insertions by position (reverse order to insert from end)
                # This way later insertions go first, maintaining relative order
                insert_ops_sorted = sorted(insert_ops, key=lambda x: x['position'], reverse=True)
                
                for op in insert_ops_sorted:
                    # Insert at end of document
                    # Note: This is a simplification - ideally we'd find the exact insertion point
                    # but that requires complex position mapping
                    requests.append({
                        'insertText': {
                            'location': {'index': end_index - 1},
                            'text': op['new_text'] + '\n'  # Add newline for readability
                        }
                    })
            
            # Execute batch update if we have requests
            if requests:
                # Limit to 100 requests per batch (Google Docs API limit)
                batch_size = 100
                for i in range(0, len(requests), batch_size):
                    batch = requests[i:i + batch_size]
                    service.documents().batchUpdate(
                        documentId=doc_id,
                        body={'requests': batch}
                    ).execute()
            
        except HttpError as e:
            raise Exception(f"Error applying partial updates to Google Doc: {str(e)}")
    
    def update_document_content_partial(self, doc_id: str, old_content: str, new_content: str, apply_formatting: bool = True) -> None:
        """
        Update Google Doc with partial updates that preserve formatting.
        
        Flow: Agent generates markdown → Convert to Google Docs format → Apply partial update
        
        Args:
            doc_id: Google Doc ID
            old_content: Previous content (plain text) that was in the document
            new_content: New content (can include markdown formatting if apply_formatting=True)
            apply_formatting: If True, parse markdown and apply formatting (default: True)
        """
        try:
            # Convert markdown to plain text if formatting is enabled
            if apply_formatting:
                # Check if content contains markdown
                has_markdown = bool(re.search(r'[#*_`-]|^\d+\.', new_content, re.MULTILINE))
                if has_markdown:
                    # Convert markdown to plain text for partial update
                    # Note: Partial updates preserve existing formatting, so we extract plain text
                    plain_new_content, _ = self.convert_markdown_to_google_docs_format(new_content)
                    new_content = plain_new_content
                    # For partial updates with formatting, fall back to full replacement
                    logger.info("Markdown detected in partial update, using full replacement to apply formatting")
                    self.update_document_content(doc_id, new_content, apply_formatting=True)
                    return
            
            # Use partial update method for plain text
            self._apply_partial_updates(doc_id, old_content, new_content)
        except Exception as e:
            # Fall back to full replacement if partial update fails
            logger.warning(f"Partial update failed, falling back to full replacement: {e}")
            self.update_document_content(doc_id, new_content, apply_formatting=apply_formatting)
    
    def convert_markdown_to_google_docs_format(self, markdown_content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Convert markdown content to Google Docs API formatting requests.
        
        This is the core conversion function that takes markdown generated by the AI agent
        and converts it to Google Docs API format requests for insertion/update.
        
        Flow: Agent generates markdown → This function converts to Google Docs format → Insert/Update
        
        Supports:
        - Headings: # H1, ## H2, ### H3, #### H4, ##### H5, ###### H6
        - Bold: **text** or __text__
        - Italic: *text* or _text_ (but not if part of bold)
        - Bullet lists: - item or * item
        - Numbered lists: 1. item
        - Inline code: `code`
        
        Args:
            markdown_content: Markdown content generated by the AI agent
        
        Returns:
            Tuple of (plain_text, formatting_requests) where:
            - plain_text: Text without markdown markers
            - formatting_requests: List of Google Docs API batchUpdate requests
        """
        formatting_requests = []
        lines = markdown_content.split('\n')
        plain_lines = []
        paragraph_formats = []  # (line_index, type, level) - will recalculate indices after inline processing
        
        # First pass: process line-level formatting (headings, lists) and preserve all newlines
        for line_idx, line in enumerate(lines):
            plain_line = line
            line_stripped = line.strip()
            
            # Check for headings (must have # followed by space and text)
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match and len(heading_match.group(2).strip()) > 0:
                level = min(len(heading_match.group(1)), 6)
                heading_text = heading_match.group(2)
                plain_line = heading_text
                paragraph_formats.append((line_idx, 'heading', level))
            
            # Check for bullet lists (must start with - or * followed by space, and have content)
            elif re.match(r'^[-*]\s+', line) and len(line_stripped) > 2:
                plain_line = re.sub(r'^[-*]\s+', '', line)
                paragraph_formats.append((line_idx, 'bullet', None))
            
            # Check for numbered lists (must start with number, period, space, and have content)
            # Be strict: must match pattern "1. " or "123. " at start of line
            elif re.match(r'^\d+\.\s+', line) and len(line_stripped) > 3:
                # Additional check: make sure it's not just a decimal number in text
                # The pattern should be at the very start of the line
                match = re.match(r'^(\d+)\.\s+(.+)$', line)
                if match and len(match.group(2).strip()) > 0:
                    plain_line = match.group(2)  # Use the text after "number. "
                    paragraph_formats.append((line_idx, 'numbered', None))
            
            # Regular paragraph - no special formatting, just preserve as-is
            # Always preserve the line (even if empty) and add newline
            plain_lines.append(plain_line)
        
        # Join lines with newlines to preserve spacing
        plain_text = '\n'.join(plain_lines)
        if markdown_content.endswith('\n'):
            plain_text += '\n'
        
        # Second pass: process inline formatting (bold, italic, code)
        # Track inline formats with original positions, then adjust after removal
        inline_formats_raw = []  # (start, end, type, text) in original plain_text
        
        # Process code first (to avoid conflicts)
        for match in re.finditer(r'`([^`]+)`', plain_text):
            inline_formats_raw.append((match.start(), match.end(), 'code', match.group(1)))
        
        # Process bold (**text** or __text__)
        for match in re.finditer(r'\*\*([^*]+)\*\*|__([^_]+)__', plain_text):
            text = match.group(1) or match.group(2)
            inline_formats_raw.append((match.start(), match.end(), 'bold', text))
        
        # Process italic (*text* or _text_, avoiding bold conflicts)
        italic_pattern = r'(?<!\*)\*([^*\n]+)\*(?!\*)|(?<!_)_([^_\n]+)_(?!_)'
        for match in re.finditer(italic_pattern, plain_text):
            text = match.group(1) or match.group(2)
            # Check if it overlaps with any bold span
            overlaps_bold = any(s <= match.start() < e or s < match.end() <= e 
                              for s, e, t, _ in inline_formats_raw if t == 'bold')
            if not overlaps_bold:
                inline_formats_raw.append((match.start(), match.end(), 'italic', text))
        
        # Sort by start position (reverse) to process from end to start
        inline_formats_raw.sort(key=lambda x: x[0], reverse=True)
        
        # Remove inline formatting markers and calculate adjusted positions
        inline_formats = []  # (start, end, type) in final plain_text
        offset = 0
        
        for orig_start, orig_end, fmt_type, text in inline_formats_raw:
            # Calculate new positions after previous removals
            new_start = orig_start - offset
            new_end = new_start + len(text)
            
            # Track the format
            inline_formats.append((new_start, new_end, fmt_type))
            
            # Remove the markers from plain_text
            plain_text = plain_text[:orig_start] + text + plain_text[orig_end:]
            
            # Update offset for next iteration
            marker_length = orig_end - orig_start
            text_length = len(text)
            offset += marker_length - text_length
        
        # Reverse inline_formats to process in document order
        inline_formats.reverse()
        
        # Build formatting requests following Google Docs API style
        # Calculate paragraph positions in FINAL plain_text (after inline formatting removal)
        # Split final plain_text to get actual line positions
        final_lines = plain_text.split('\n')
        line_starts = []
        current_pos = 1  # Start after required first element
        for i, line in enumerate(final_lines):
            line_starts.append(current_pos)
            # Add line length + newline (except for last line if no trailing newline)
            if i < len(final_lines) - 1 or markdown_content.endswith('\n'):
                current_pos += len(line) + 1  # +1 for newline
            else:
                current_pos += len(line)  # Last line without trailing newline
        
        # Debug: log what we're formatting
        logger.debug(f"Converting markdown: {len(paragraph_formats)} paragraph formats, {len(inline_formats)} inline formats")
        logger.debug(f"Paragraph formats: {paragraph_formats[:5]}...")  # Show first 5
        
        # Paragraph-level formatting
        # For Google Docs API, paragraph ranges should NOT include the newline for list formatting
        # The newline is part of the paragraph separator, not the paragraph itself
        for line_idx, fmt_type, level in paragraph_formats:
            if line_idx < len(line_starts):
                line_start = line_starts[line_idx]
                line_text = final_lines[line_idx] if line_idx < len(final_lines) else ''
                
                # For paragraph formatting, endIndex should be exclusive (just after the last character)
                # Don't include the newline in the range for list/heading formatting
                line_end = line_start + len(line_text)
                
                # Validate range is valid
                if line_end <= line_start:
                    logger.warning(f"Skipping invalid range for line {line_idx}: start={line_start}, end={line_end}")
                    continue
                
                if fmt_type == 'heading':
                    # Use updateParagraphStyle for headings (matches official API style)
                    formatting_requests.append({
                        'updateParagraphStyle': {
                            'range': {
                                'startIndex': line_start,
                                'endIndex': line_end
                            },
                            'paragraphStyle': {
                                'namedStyleType': f'HEADING_{level}'
                            },
                            'fields': 'namedStyleType'
                        }
                    })
                elif fmt_type == 'bullet':
                    # Use createParagraphBullets for bullet lists
                    formatting_requests.append({
                        'createParagraphBullets': {
                            'range': {
                                'startIndex': line_start,
                                'endIndex': line_end
                            },
                            'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                        }
                    })
                elif fmt_type == 'numbered':
                    # Use createParagraphBullets for numbered lists
                    formatting_requests.append({
                        'createParagraphBullets': {
                            'range': {
                                'startIndex': line_start,
                                'endIndex': line_end
                            },
                            'bulletPreset': 'NUMBERED_DECIMAL_ALPHA_ROMAN'
                        }
                    })
        
        # Inline formatting (character-level)
        for start, end, fmt_type in inline_formats:
            if fmt_type == 'bold':
                # Use updateTextStyle for bold (matches official API style)
                formatting_requests.append({
                    'updateTextStyle': {
                        'range': {
                            'startIndex': start,
                            'endIndex': end
                        },
                        'textStyle': {
                            'bold': True
                        },
                        'fields': 'bold'
                    }
                })
            elif fmt_type == 'italic':
                # Use updateTextStyle for italic (matches official API style)
                formatting_requests.append({
                    'updateTextStyle': {
                        'range': {
                            'startIndex': start,
                            'endIndex': end
                        },
                        'textStyle': {
                            'italic': True
                        },
                        'fields': 'italic'
                    }
                })
            elif fmt_type == 'code':
                # Use updateTextStyle for code formatting (monospace font)
                formatting_requests.append({
                    'updateTextStyle': {
                        'range': {
                            'startIndex': start,
                            'endIndex': end
                        },
                        'textStyle': {
                            'weightedFontFamily': {
                                'fontFamily': 'Courier New'
                            }
                        },
                        'fields': 'weightedFontFamily'
                    }
                })
        
        return plain_text, formatting_requests
    
    def update_document_content(self, doc_id: str, new_content: str, apply_formatting: bool = True):
        """
        Update Google Doc with new content, converting markdown to Google Docs format.
        
        Flow: Agent generates markdown → Convert to Google Docs format → Insert/Update document
        
        Args:
            doc_id: Google Doc ID
            new_content: Markdown content generated by the AI agent (or plain text)
            apply_formatting: If True, parse markdown and apply Google Docs formatting (default: True)
        """
        try:
            service = self._get_google_docs_service()
            
            # Get current document to find end index
            doc = service.documents().get(documentId=doc_id).execute()
            end_index = doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)
            
            # Clear existing content (except first element which is required)
            requests = []
            if end_index > 1:
                requests.append({
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': end_index - 1
                        }
                    }
                })
            
            # Step 1: Convert markdown to Google Docs format
            # Agent generates markdown → Convert to Google Docs API format requests
            if apply_formatting:
                plain_text, formatting_requests = self.convert_markdown_to_google_docs_format(new_content)
                logger.debug(f"Converted markdown to {len(formatting_requests)} Google Docs formatting requests")
            else:
                plain_text = new_content
                formatting_requests = []
            
            # Step 2: Insert plain text content
            requests.append({
                'insertText': {
                    'location': {'index': 1},
                    'text': plain_text
                }
            })
            
            # Step 3: Apply formatting requests (headings, bold, italic, lists, etc.)
            requests.extend(formatting_requests)
            
            # Step 4: Execute batch update (matches official Google Docs API style)
            if requests:
                result = service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()
                logger.info(f"Updated document {doc_id}: inserted {len(plain_text)} chars, applied {len(formatting_requests)} formatting requests")
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
            
            # If initial content provided, add it (supports markdown formatting)
            if initial_content:
                self.update_document_content(doc_id, initial_content, apply_formatting=True)
            
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
