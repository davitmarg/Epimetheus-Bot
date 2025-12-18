import React, { useState, useEffect } from 'react';

import { FileText, MessageSquare, Settings, History, RefreshCw, AlertCircle, CheckCircle, Clock, Zap, Copy, X } from 'lucide-react';
import EpimetheusLogo from './EpimetheusLogo';
import { 
  getDocumentsData, 
  forceUpdate, 
  revertVersion, 
  getVersionHistory,
  getMessageCount,
  syncDriveFolder
} from '../utils/api';

// Generate a unique user ID
const generateUserId = () => {
  return `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

// Get or create user ID from localStorage
const getUserId = () => {
  let userId = localStorage.getItem('epimetheus_userId');
  if (!userId) {
    userId = generateUserId();
    localStorage.setItem('epimetheus_userId', userId);
  }
  return userId;
};


export default function EpimetheusDashboard() {
  const [userId] = useState(() => getUserId());
  const [activeTab, setActiveTab] = useState('dashboard');
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentForHistory, setSelectedDocumentForHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [totalMessageCount, setTotalMessageCount] = useState(0);

  // Fetch documents from API on mount
  useEffect(() => {
    fetchDocuments();
  }, []);


  const fetchDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const [documentsData, messageCountData] = await Promise.all([
        getDocumentsData(),
        getMessageCount()
      ]);
      setDocuments(documentsData);
      setTotalMessageCount(messageCountData.count || 0);
    } catch (err) {
      console.error('Error fetching documents:', err);
      setError('Failed to load documents. Please check if the backend API is running.');
      // Keep empty array on error
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  const refreshDocuments = async () => {
    setRefreshing(true);
    await fetchDocuments();
    setRefreshing(false);
  };

  const handleResyncDrive = async () => {
    try {
      setRefreshing(true);
      await syncDriveFolder();
      // Refresh documents after sync
      await fetchDocuments();
      alert('Google Drive documents synced successfully!');
    } catch (err) {
      console.error('Error syncing Drive:', err);
      alert(`Failed to sync Drive: ${err.message}`);
    } finally {
      setRefreshing(false);
    }
  };

  const handleForceUpdate = async (documentId) => {
    try {
      await forceUpdate(documentId);
      // Refresh the document data to get updated information
      const updatedDocuments = await getDocumentsData();
      setDocuments(updatedDocuments);
      alert('Document update triggered successfully!');
    } catch (err) {
      console.error('Error forcing update:', err);
      alert(`Failed to trigger update: ${err.message}`);
    }
  };

  const handleRevert = (documentId) => {
    setSelectedDocumentForHistory(documentId);
    setActiveTab('history');
  };

  const handleRevertVersion = async (documentId, version, versionId) => {
    if (!confirm(`Are you sure you want to revert to version ${version}?`)) {
      return;
    }
    try {
      // Use versionId (UUID) if available, otherwise fall back to version number
      const idToUse = versionId || version.toString();
      await revertVersion(documentId, idToUse);
      // Refresh documents to get updated data
      await fetchDocuments();
      alert(`Successfully reverted to version ${version}`);
    } catch (err) {
      console.error('Error reverting version:', err);
      alert(`Failed to revert version: ${err.message}`);
    }
  };


  const handleDeleteDocument = (documentId) => {
    // Note: This only removes from local view. The document will reappear on refresh
    // since there's no delete endpoint in the backend API.
    if (confirm('Are you sure you want to remove this document from view?')) {
      setDocuments(prev => prev.filter(doc => doc.id !== documentId));
    }
  };

  const copyUserId = () => {
    navigator.clipboard.writeText(userId);
    alert('User ID copied to clipboard!');
  };

  const formatTimeAgo = (timestamp) => {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days !== 1 ? 's' : ''} ago`;
  };



  return (

    <div className="min-h-screen" style={{ backgroundColor: '#1D1C1D' }}>

      {/* Header */}

      <header className="border-b" style={{ backgroundColor: '#350D36', borderColor: '#3F0E40' }}>

        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">

          <div className="flex items-center gap-3">

            <div className="flex items-center justify-center">

              <EpimetheusLogo className="w-12 h-12" />

            </div>

            <div>

              <h1 className="text-2xl font-bold text-white">Epimetheus</h1>

              <p className="text-sm" style={{ color: '#D1D2D3' }}>Slack → Docs Automation</p>

            </div>

          </div>

          <div className="flex items-center gap-2">

            <button 

              onClick={refreshDocuments}

              disabled={refreshing || loading}

              className="text-white px-4 py-2 rounded font-medium flex items-center gap-2 transition-colors hover:opacity-90 disabled:opacity-50"

              style={{ backgroundColor: '#611f69' }}

              title="Refresh documents"

            >

              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />

              Refresh

            </button>

            <button 

              onClick={handleResyncDrive}

              disabled={refreshing || loading}

              className="text-white px-4 py-2 rounded font-medium flex items-center gap-2 transition-colors hover:opacity-90 disabled:opacity-50 border"

              style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}

              title="Resync Google Drive documents"

            >

              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />

              Resync Drive

            </button>

          </div>

        </div>

      </header>



      {/* Navigation */}

      <nav className="max-w-7xl mx-auto px-6 py-4">

        <div className="flex gap-2">

          {['dashboard', 'history', 'settings'].map((tab) => (

            <button

              key={tab}

              onClick={() => setActiveTab(tab)}

              className={`px-4 py-2 rounded capitalize transition-colors font-medium ${

                activeTab === tab

                  ? 'text-white'

                  : 'hover:opacity-80'

              }`}

              style={

                activeTab === tab

                  ? { backgroundColor: '#4A154B', color: '#FFFFFF' }

                  : { backgroundColor: 'transparent', color: '#D1D2D3' }

              }

            >

              {tab}

            </button>

          ))}

        </div>

      </nav>



      {/* Main Content */}

      <main className="max-w-7xl mx-auto px-6 py-6">

        {activeTab === 'dashboard' && (

          <div className="space-y-6">

            {/* Error Message */}

            {error && (

              <div className="rounded-lg p-4 border flex items-center gap-3" style={{ backgroundColor: '#E01E5A20', borderColor: '#E01E5A40' }}>

                <AlertCircle className="w-5 h-5" style={{ color: '#E01E5A' }} />

                <div className="flex-1">

                  <p className="text-white font-medium">Error loading documents</p>

                  <p className="text-sm" style={{ color: '#D1D2D3' }}>{error}</p>

                </div>

                <button

                  onClick={fetchDocuments}

                  className="text-white px-3 py-1 rounded text-sm font-medium transition-colors hover:opacity-90"

                  style={{ backgroundColor: '#611f69' }}

                >

                  Retry

                </button>

              </div>

            )}

            {/* Loading State */}

            {loading && !error && (

              <div className="rounded-lg p-12 border text-center" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

                <RefreshCw className="w-12 h-12 mx-auto mb-4 animate-spin" style={{ color: '#8B5FBF' }} />

                <p className="text-white">Loading documents...</p>

              </div>

            )}

            {/* Stats Cards - Only show when not loading */}

            {!loading && (

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

              <div className="rounded-lg p-6 border" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

                <div className="flex items-center gap-3 mb-2">

                  <MessageSquare className="w-5 h-5" style={{ color: '#8B5FBF' }} />

                  <span className="text-sm" style={{ color: '#D1D2D3' }}>Total Messages</span>

                </div>

                <div className="text-3xl font-bold text-white">

                  {totalMessageCount.toLocaleString()}

                </div>

                <div className="text-sm mt-1" style={{ color: '#9CA3AF' }}>Total messages received</div>

              </div>



              <div className="rounded-lg p-6 border" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

                <div className="flex items-center gap-3 mb-2">

                  <FileText className="w-5 h-5" style={{ color: '#8B5FBF' }} />

                  <span className="text-sm" style={{ color: '#D1D2D3' }}>Active Documents</span>

                </div>

                <div className="text-3xl font-bold text-white">{documents.length}</div>

                <div className="text-sm mt-1" style={{ color: '#9CA3AF' }}>

                  {documents.filter(doc => doc.status === 'active').length} documents

                </div>

              </div>



              <div className="rounded-lg p-6 border" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

                <div className="flex items-center gap-3 mb-2">

                  <RefreshCw className="w-5 h-5" style={{ color: '#2EB67D' }} />

                  <span className="text-sm" style={{ color: '#D1D2D3' }}>Total Versions</span>

                </div>

                <div className="text-3xl font-bold text-white">

                  {documents.reduce((sum, doc) => sum + (doc.versions?.length || 0), 0)}

                </div>

                <div className="text-sm mt-1" style={{ color: '#9CA3AF' }}>Document updates</div>

              </div>

            </div>

            )}

            {/* Document List */}

            {!loading && (

            <div className="space-y-4">

              <h2 className="text-xl font-semibold text-white">Active Documents</h2>

              {documents.length === 0 ? (

                <div className="rounded-lg p-12 border text-center" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

                  <MessageSquare className="w-16 h-16 mx-auto mb-4 opacity-50" style={{ color: '#9CA3AF' }} />

                  <h3 className="text-lg font-semibold text-white mb-2">No documents yet</h3>

                  <p className="mb-6" style={{ color: '#D1D2D3' }}>Use "Resync Drive" to load documents from your Google Drive folder.</p>

                </div>

              ) : (

                documents.map((document) => (

                <div

                  key={document.id}

                  className="rounded-lg p-6 border transition-colors hover:opacity-90"

                  style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}

                >

                  <div className="flex items-start justify-between mb-4">

                    <div className="flex-1">

                      <div className="flex items-center gap-3 mb-2">

                        <h3 className="text-lg font-semibold text-white">{document.name}</h3>

                        <span className="flex items-center gap-1 text-xs px-2 py-1 rounded-full" style={{ backgroundColor: '#2EB67D20', color: '#2EB67D' }}>

                          <CheckCircle className="w-3 h-3" />

                          {document.status}

                        </span>

                      </div>

                      <a 

                        href={document.docUrl}

                        target="_blank"

                        rel="noopener noreferrer"

                        className="text-sm underline hover:opacity-80"

                        style={{ color: '#8B5FBF' }}

                      >

                        View Google Doc →

                      </a>

                    </div>

                    <div className="flex gap-2">

                      <button

                        onClick={() => handleForceUpdate(document.id)}

                        className="text-white px-3 py-2 rounded font-medium flex items-center gap-2 transition-colors text-sm hover:opacity-90"

                        style={{ backgroundColor: '#611f69' }}

                      >

                        <RefreshCw className="w-4 h-4" />

                        Force Update

                      </button>

                      <button

                        onClick={() => handleRevert(document.id)}

                        className="text-white px-3 py-2 rounded font-medium flex items-center gap-2 transition-colors text-sm border hover:opacity-80"

                        style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40', color: '#D1D2D3' }}

                      >

                        <History className="w-4 h-4" />

                        History

                      </button>

                      <button

                        onClick={() => handleDeleteDocument(document.id)}

                        className="px-3 py-2 rounded font-medium flex items-center gap-2 transition-colors text-sm border hover:opacity-80"

                        style={{ backgroundColor: '#E01E5A20', borderColor: '#E01E5A40', color: '#E01E5A' }}

                        title="Remove Document"

                      >

                        <X className="w-4 h-4" />

                      </button>

                    </div>

                  </div>



                  {/* Action Count */}
                  <div className="rounded-lg p-4 border" style={{ backgroundColor: '#1D1C1D', borderColor: '#3F0E40' }}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Zap className="w-4 h-4" style={{ color: '#8B5FBF' }} />
                        <span className="text-sm" style={{ color: '#D1D2D3' }}>Actions/Changes</span>
                      </div>
                      <span className="text-xl font-bold text-white">
                        {document.actionCount || document.versions?.length || 0}
                      </span>
                    </div>
                    <p className="text-xs mt-1" style={{ color: '#9CA3AF' }}>
                      Document has been updated {document.actionCount || document.versions?.length || 0} time{document.actionCount !== 1 ? 's' : ''}
                    </p>
                  </div>

                  {/* Stats */}

                  <div className="grid grid-cols-2 gap-4 mt-4">

                    <div className="flex items-center gap-2 text-sm" style={{ color: '#D1D2D3' }}>

                      <MessageSquare className="w-4 h-4" />

                      {document.messageCount} messages tracked

                    </div>

                    <div className="flex items-center gap-2 text-sm" style={{ color: '#D1D2D3' }}>

                      <Clock className="w-4 h-4" />

                      Updated {document.lastUpdate}

                    </div>

                  </div>

                </div>

              )))}

            </div>

            )}

          </div>

        )}



        {activeTab === 'history' && (

          <div className="space-y-6">

            <div className="rounded-lg p-8 border" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

              <div className="flex items-center justify-between mb-4">

                <div>

                  <h2 className="text-2xl font-semibold text-white mb-2">Version History</h2>

                  <p className="text-gray-400">View and revert to previous document versions.</p>

                </div>

                {selectedDocumentForHistory && (

                  <button

                    onClick={() => setSelectedDocumentForHistory(null)}

                    className="flex items-center gap-2 hover:opacity-80"

                    style={{ color: '#D1D2D3' }}

                  >

                    <X className="w-4 h-4" />

                    Clear filter

                  </button>

                )}

              </div>

              {!selectedDocumentForHistory && documents.length > 0 && (

                <div className="mb-6">

                  <label className="block text-sm font-medium mb-2" style={{ color: '#D1D2D3' }}>

                    Filter by Document

                  </label>

                  <select

                    onChange={(e) => setSelectedDocumentForHistory(e.target.value || null)}

                    className="rounded-lg px-4 py-2 text-white w-full focus:outline-none focus:ring-2"

                    style={{ backgroundColor: '#1D1C1D', borderColor: '#3F0E40', borderWidth: '1px', focusRingColor: '#8B5FBF' }}

                  >

                    <option value="">All Documents</option>

                    {documents.map(doc => (

                      <option key={doc.id} value={doc.id}>{doc.name}</option>

                    ))}

                  </select>

                </div>

              )}

              <div className="mt-6 space-y-3">

                {(() => {

                  const documentsToShow = selectedDocumentForHistory

                    ? documents.filter(doc => doc.id === selectedDocumentForHistory)

                    : documents;

                  const allVersions = documentsToShow.flatMap(doc =>

                    (doc.versions || []).map(v => ({ ...v, documentId: doc.id, documentName: doc.name }))

                  ).sort((a, b) => b.timestamp - a.timestamp);

                  if (allVersions.length === 0) {

                    return (

                      <div className="text-center py-8" style={{ color: '#D1D2D3' }}>

                        <History className="w-12 h-12 mx-auto mb-3 opacity-50" />

                        <p>No version history available yet.</p>

                      </div>

                    );

                  }

                  return allVersions.map((version, idx) => (

                    <div key={idx} className="rounded-lg p-4 border flex items-center justify-between" style={{ backgroundColor: '#1D1C1D', borderColor: '#3F0E40' }}>

                      <div className="flex-1">

                        <div className="flex items-center gap-3 mb-1">

                          <div className="text-white font-medium">Version {version.version}</div>

                          <span className="text-xs" style={{ color: '#9CA3AF' }}>•</span>

                          <span className="text-sm" style={{ color: '#8B5FBF' }}>{version.documentName}</span>

                        </div>

                        <div className="text-sm" style={{ color: '#D1D2D3' }}>

                          {formatTimeAgo(version.timestamp)} • {version.charsAdded.toLocaleString()} chars added

                        </div>

                      </div>

                      <button

                        onClick={() => handleRevertVersion(version.documentId, version.version, version.versionId)}

                        className="text-white px-3 py-1.5 rounded text-sm font-medium transition-colors hover:opacity-90"

                        style={{ backgroundColor: '#611f69' }}

                      >

                        Revert

                      </button>

                    </div>

                  ));

                })()}

              </div>

            </div>

          </div>

        )}



        {activeTab === 'settings' && (

          <div className="rounded-lg p-8 border" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

            <h2 className="text-2xl font-semibold text-white mb-6">Settings</h2>

            <div className="space-y-6">

              <div>

                <label className="block text-sm font-medium mb-2" style={{ color: '#D1D2D3' }}>

                  User ID

                </label>

                <div className="flex gap-2">

                  <input

                    type="text"

                    value={userId}

                    readOnly

                    className="rounded-lg px-4 py-2 w-full font-mono text-sm"

                    style={{ backgroundColor: '#1D1C1D', borderColor: '#3F0E40', borderWidth: '1px', color: '#D1D2D3' }}

                  />

                  <button

                    onClick={copyUserId}

                    className="rounded-lg px-4 py-2 text-white flex items-center gap-2 transition-colors hover:opacity-80 border"

                    style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}

                    title="Copy User ID"

                  >

                    <Copy className="w-4 h-4" />

                  </button>

                </div>

                <p className="text-sm mt-1" style={{ color: '#9CA3AF' }}>Your unique identifier - used to keep your data separate from other users</p>

              </div>

              <div className="pt-4 border-t" style={{ borderColor: '#3F0E40' }}>

                <h3 className="text-lg font-semibold text-white mb-4">About Epimetheus</h3>

                <div className="space-y-2 text-sm" style={{ color: '#D1D2D3' }}>

                  <p>Epimetheus automatically tracks Slack messages and updates Google Docs.</p>

                  <p>Your data is isolated using your User ID. No authentication required - just start using it!</p>

                  <p className="pt-2 text-xs" style={{ color: '#9CA3AF' }}>

                    Data is stored locally in your browser. When you connect to the backend, your User ID will be used to sync your documents.

                  </p>

                </div>

              </div>

            </div>

          </div>

        )}

      </main>




    </div>

  );

}


