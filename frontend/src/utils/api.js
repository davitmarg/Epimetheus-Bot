/**
 * API utility functions for Epimetheus
 * 
 * Connects to the Epimetheus backend API
 */

// Use relative URL when in production (Docker), absolute for local dev
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 
  (import.meta.env.PROD ? '/api/v1' : 'http://localhost:8000/api/v1');

/**
 * Get the current user ID from localStorage
 */
export const getUserId = () => {
  return localStorage.getItem('epimetheus_userId');
};

/**
 * Get API service status
 */
export const getStatus = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/status`);
    if (!response.ok) throw new Error('Failed to fetch status');
    return await response.json();
  } catch (error) {
    console.error('Error fetching status:', error);
    throw error;
  }
};

/**
 * Get all documents (channels)
 */
export const getDocuments = async (folderId = null) => {
  try {
    const url = folderId 
      ? `${API_BASE_URL}/documents?folder_id=${folderId}`
      : `${API_BASE_URL}/documents`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch documents');
    return await response.json();
  } catch (error) {
    console.error('Error fetching documents:', error);
    // Return empty array on error - will fall back to localStorage
    return { documents: [] };
  }
};

/**
 * Get all document metadata
 */
export const getAllMetadata = async (folderId = null) => {
  try {
    const url = folderId 
      ? `${API_BASE_URL}/documents/metadata/all?folder_id=${folderId}`
      : `${API_BASE_URL}/documents/metadata/all`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch metadata');
    return await response.json();
  } catch (error) {
    console.error('Error fetching metadata:', error);
    return { documents: [], count: 0 };
  }
};

/**
 * Create a new document
 */
export const createDocument = async (documentData) => {
  try {
    const response = await fetch(`${API_BASE_URL}/documents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: documentData.name,
        folder_id: documentData.folder_id || null,
        initial_content: documentData.initial_content || '',
        tags: documentData.tags || [],
        description: documentData.description || '',
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create document');
    }
    return await response.json();
  } catch (error) {
    console.error('Error creating document:', error);
    throw error;
  }
};

/**
 * Get a specific document
 */
export const getDocument = async (docId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/documents/${docId}`);
    if (!response.ok) throw new Error('Failed to fetch document');
    return await response.json();
  } catch (error) {
    console.error('Error fetching document:', error);
    throw error;
  }
};

/**
 * Update document metadata
 */
export const updateMetadata = async (docId, metadata) => {
  try {
    const response = await fetch(`${API_BASE_URL}/documents/${docId}/metadata`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: metadata.name,
        tags: metadata.tags,
        description: metadata.description,
      }),
    });
    if (!response.ok) throw new Error('Failed to update metadata');
    return await response.json();
  } catch (error) {
    console.error('Error updating metadata:', error);
    throw error;
  }
};

/**
 * Force update a document (manual trigger)
 */
export const forceUpdate = async (docId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/trigger`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ doc_id: docId }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to force update');
    }
    return await response.json();
  } catch (error) {
    console.error('Error forcing update:', error);
    throw error;
  }
};

/**
 * Get version history for a document
 */
export const getVersionHistory = async (docId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/versions/${docId}`);
    if (!response.ok) throw new Error('Failed to fetch version history');
    return await response.json();
  } catch (error) {
    console.error('Error fetching version history:', error);
    throw error;
  }
};

/**
 * Get a specific version of a document
 */
export const getVersion = async (docId, versionId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/versions/${docId}/${versionId}`);
    if (!response.ok) throw new Error('Failed to fetch version');
    return await response.json();
  } catch (error) {
    console.error('Error fetching version:', error);
    throw error;
  }
};

/**
 * Revert to a previous version
 */
export const revertVersion = async (docId, versionId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/revert/${docId}/${versionId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to revert version');
    }
    return await response.json();
  } catch (error) {
    console.error('Error reverting version:', error);
    throw error;
  }
};

/**
 * Search documents
 */
export const searchDocuments = async (query, folderId = null) => {
  try {
    const url = folderId 
      ? `${API_BASE_URL}/documents/search?query=${encodeURIComponent(query)}&folder_id=${folderId}`
      : `${API_BASE_URL}/documents/search?query=${encodeURIComponent(query)}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to search documents');
    return await response.json();
  } catch (error) {
    console.error('Error searching documents:', error);
    throw error;
  }
};

/**
 * Sync Drive folder to mapping
 */
export const syncDriveFolder = async (folderId = null) => {
  try {
    const url = folderId 
      ? `${API_BASE_URL}/drive/mapping/sync?folder_id=${folderId}`
      : `${API_BASE_URL}/drive/mapping/sync`;
    const response = await fetch(url, { method: 'POST' });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to sync Drive folder');
    }
    return await response.json();
  } catch (error) {
    console.error('Error syncing Drive folder:', error);
    throw error;
  }
};

/**
 * Get Drive mapping
 */
export const getDriveMapping = async (folderId = null) => {
  try {
    const url = folderId 
      ? `${API_BASE_URL}/drive/mapping?folder_id=${folderId}`
      : `${API_BASE_URL}/drive/mapping`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch Drive mapping');
    return await response.json();
  } catch (error) {
    console.error('Error fetching Drive mapping:', error);
    throw error;
  }
};
