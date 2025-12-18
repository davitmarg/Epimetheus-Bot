import React, { useState, useEffect } from 'react';

import { FileText, MessageSquare, Settings, History, Plus, RefreshCw, AlertCircle, CheckCircle, Clock, Zap, Copy, X } from 'lucide-react';
import EpimetheusLogo from './EpimetheusLogo';

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

// Load channels from localStorage
const loadChannels = (userId) => {
  const stored = localStorage.getItem(`epimetheus_channels_${userId}`);
  if (stored) {
    return JSON.parse(stored);
  }
  // Return default demo data
  return [
    {
      id: 1,
      name: '#engineering-docs',
      status: 'active',
      messageCount: 247,
      lastUpdate: '2 hours ago',
      docUrl: 'https://docs.google.com/document/d/example1',
      threshold: 10000,
      currentChars: 7234,
      slackChannelId: '',
      versions: [
        { version: 3, timestamp: Date.now() - 10800000, charsAdded: 2340 },
        { version: 2, timestamp: Date.now() - 21600000, charsAdded: 1890 },
        { version: 1, timestamp: Date.now() - 32400000, charsAdded: 1520 }
      ]
    },
    {
      id: 2,
      name: '#product-specs',
      status: 'active',
      messageCount: 156,
      lastUpdate: '5 hours ago',
      docUrl: 'https://docs.google.com/document/d/example2',
      threshold: 10000,
      currentChars: 3421,
      slackChannelId: '',
      versions: [
        { version: 2, timestamp: Date.now() - 18000000, charsAdded: 2100 },
        { version: 1, timestamp: Date.now() - 36000000, charsAdded: 1321 }
      ]
    }
  ];
};

// Save channels to localStorage
const saveChannels = (userId, channels) => {
  localStorage.setItem(`epimetheus_channels_${userId}`, JSON.stringify(channels));
};

export default function EpimetheusDashboard() {
  const [userId] = useState(() => getUserId());
  const [activeTab, setActiveTab] = useState('dashboard');
  const [channels, setChannels] = useState(() => loadChannels(userId));
  const [showAddChannel, setShowAddChannel] = useState(false);
  const [selectedChannelForHistory, setSelectedChannelForHistory] = useState(null);
  const [defaultThreshold, setDefaultThreshold] = useState(() => {
    const stored = localStorage.getItem(`epimetheus_threshold_${userId}`);
    return stored ? parseInt(stored, 10) : 10000;
  });

  // Save channels whenever they change
  useEffect(() => {
    saveChannels(userId, channels);
  }, [channels, userId]);

  // Save threshold when it changes
  useEffect(() => {
    localStorage.setItem(`epimetheus_threshold_${userId}`, defaultThreshold.toString());
  }, [defaultThreshold, userId]);

  const handleForceUpdate = async (channelId) => {
    // TODO: Connect to backend API
    // For now, simulate the update
    setChannels(prev => prev.map(ch => {
      if (ch.id === channelId) {
        return {
          ...ch,
          currentChars: 0,
          lastUpdate: 'just now',
          messageCount: ch.messageCount + 1,
          versions: [
            {
              version: (ch.versions?.[0]?.version || 0) + 1,
              timestamp: Date.now(),
              charsAdded: ch.currentChars
            },
            ...(ch.versions || [])
          ]
        };
      }
      return ch;
    }));
  };

  const handleRevert = (channelId) => {
    setSelectedChannelForHistory(channelId);
    setActiveTab('history');
  };

  const handleRevertVersion = async (channelId, version) => {
    // TODO: Connect to backend API
    alert(`Reverting channel ${channelId} to version ${version}...`);
  };

  const handleAddChannel = (formData) => {
    const newChannel = {
      id: Date.now(),
      name: formData.channelName,
      status: 'active',
      messageCount: 0,
      lastUpdate: 'never',
      docUrl: formData.docUrl,
      threshold: defaultThreshold,
      currentChars: 0,
      slackChannelId: formData.slackChannelId || '',
      versions: []
    };
    setChannels(prev => [...prev, newChannel]);
    setShowAddChannel(false);
  };

  const handleDeleteChannel = (channelId) => {
    if (confirm('Are you sure you want to remove this channel?')) {
      setChannels(prev => prev.filter(ch => ch.id !== channelId));
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

          <button 

            onClick={() => setShowAddChannel(true)}

            className="text-white px-4 py-2 rounded font-medium flex items-center gap-2 transition-colors hover:opacity-90"

            style={{ backgroundColor: '#611f69' }}

          >

            <Plus className="w-4 h-4" />

            Add Channel

          </button>

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

            {/* Stats Cards */}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

              <div className="rounded-lg p-6 border" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

                <div className="flex items-center gap-3 mb-2">

                  <MessageSquare className="w-5 h-5" style={{ color: '#8B5FBF' }} />

                  <span className="text-sm" style={{ color: '#D1D2D3' }}>Total Messages</span>

                </div>

                <div className="text-3xl font-bold text-white">

                  {channels.reduce((sum, ch) => sum + ch.messageCount, 0).toLocaleString()}

                </div>

                <div className="text-sm mt-1" style={{ color: '#9CA3AF' }}>Across all channels</div>

              </div>



              <div className="rounded-lg p-6 border" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

                <div className="flex items-center gap-3 mb-2">

                  <FileText className="w-5 h-5" style={{ color: '#8B5FBF' }} />

                  <span className="text-sm" style={{ color: '#D1D2D3' }}>Active Channels</span>

                </div>

                <div className="text-3xl font-bold text-white">{channels.length}</div>

                <div className="text-sm mt-1" style={{ color: '#9CA3AF' }}>

                  {channels.filter(ch => ch.status === 'active').length} monitoring

                </div>

              </div>



              <div className="rounded-lg p-6 border" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

                <div className="flex items-center gap-3 mb-2">

                  <RefreshCw className="w-5 h-5" style={{ color: '#2EB67D' }} />

                  <span className="text-sm" style={{ color: '#D1D2D3' }}>Total Versions</span>

                </div>

                <div className="text-3xl font-bold text-white">

                  {channels.reduce((sum, ch) => sum + (ch.versions?.length || 0), 0)}

                </div>

                <div className="text-sm mt-1" style={{ color: '#9CA3AF' }}>Document updates</div>

              </div>

            </div>



            {/* Channel List */}

            <div className="space-y-4">

              <h2 className="text-xl font-semibold text-white">Active Channels</h2>

              {channels.length === 0 ? (

                <div className="rounded-lg p-12 border text-center" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}>

                  <MessageSquare className="w-16 h-16 mx-auto mb-4 opacity-50" style={{ color: '#9CA3AF' }} />

                  <h3 className="text-lg font-semibold text-white mb-2">No channels yet</h3>

                  <p className="mb-6" style={{ color: '#D1D2D3' }}>Get started by adding your first Slack channel to track.</p>

                  <button

                    onClick={() => setShowAddChannel(true)}

                    className="text-white px-6 py-3 rounded font-medium flex items-center gap-2 transition-colors hover:opacity-90 mx-auto"

                    style={{ backgroundColor: '#611f69' }}

                  >

                    <Plus className="w-5 h-5" />

                    Add Your First Channel

                  </button>

                </div>

              ) : (

                channels.map((channel) => (

                <div

                  key={channel.id}

                  className="rounded-lg p-6 border transition-colors hover:opacity-90"

                  style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}

                >

                  <div className="flex items-start justify-between mb-4">

                    <div className="flex-1">

                      <div className="flex items-center gap-3 mb-2">

                        <h3 className="text-lg font-semibold text-white">{channel.name}</h3>

                        <span className="flex items-center gap-1 text-xs px-2 py-1 rounded-full" style={{ backgroundColor: '#2EB67D20', color: '#2EB67D' }}>

                          <CheckCircle className="w-3 h-3" />

                          {channel.status}

                        </span>

                      </div>

                      <a 

                        href={channel.docUrl}

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

                        onClick={() => handleForceUpdate(channel.id)}

                        className="text-white px-3 py-2 rounded font-medium flex items-center gap-2 transition-colors text-sm hover:opacity-90"

                        style={{ backgroundColor: '#611f69' }}

                      >

                        <RefreshCw className="w-4 h-4" />

                        Force Update

                      </button>

                      <button

                        onClick={() => handleRevert(channel.id)}

                        className="text-white px-3 py-2 rounded font-medium flex items-center gap-2 transition-colors text-sm border hover:opacity-80"

                        style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40', color: '#D1D2D3' }}

                      >

                        <History className="w-4 h-4" />

                        History

                      </button>

                      <button

                        onClick={() => handleDeleteChannel(channel.id)}

                        className="px-3 py-2 rounded font-medium flex items-center gap-2 transition-colors text-sm border hover:opacity-80"

                        style={{ backgroundColor: '#E01E5A20', borderColor: '#E01E5A40', color: '#E01E5A' }}

                        title="Remove Channel"

                      >

                        <X className="w-4 h-4" />

                      </button>

                    </div>

                  </div>



                  {/* Progress Bar */}

                  <div className="space-y-2">

                    <div className="flex items-center justify-between text-sm">

                      <span style={{ color: '#D1D2D3' }}>Progress to next update</span>

                      <span className="text-white font-mono">

                        {channel.currentChars.toLocaleString()} / {channel.threshold.toLocaleString()} chars

                      </span>

                    </div>

                    <div className="w-full rounded-full h-2 overflow-hidden" style={{ backgroundColor: '#3F0E40' }}>

                      <div

                        className="h-full rounded-full transition-all duration-500"

                        style={{ width: `${(channel.currentChars / channel.threshold) * 100}%`, backgroundColor: '#8B5FBF' }}

                      />

                    </div>

                  </div>



                  {/* Stats */}

                  <div className="grid grid-cols-2 gap-4 mt-4">

                    <div className="flex items-center gap-2 text-sm" style={{ color: '#D1D2D3' }}>

                      <MessageSquare className="w-4 h-4" />

                      {channel.messageCount} messages tracked

                    </div>

                    <div className="flex items-center gap-2 text-sm" style={{ color: '#D1D2D3' }}>

                      <Clock className="w-4 h-4" />

                      Updated {channel.lastUpdate}

                    </div>

                  </div>

                </div>

              )))}

            </div>

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

                {selectedChannelForHistory && (

                  <button

                    onClick={() => setSelectedChannelForHistory(null)}

                    className="flex items-center gap-2 hover:opacity-80"

                    style={{ color: '#D1D2D3' }}

                  >

                    <X className="w-4 h-4" />

                    Clear filter

                  </button>

                )}

              </div>

              {!selectedChannelForHistory && channels.length > 0 && (

                <div className="mb-6">

                  <label className="block text-sm font-medium mb-2" style={{ color: '#D1D2D3' }}>

                    Filter by Channel

                  </label>

                  <select

                    onChange={(e) => setSelectedChannelForHistory(e.target.value ? parseInt(e.target.value, 10) : null)}

                    className="rounded-lg px-4 py-2 text-white w-full focus:outline-none focus:ring-2"

                    style={{ backgroundColor: '#1D1C1D', borderColor: '#3F0E40', borderWidth: '1px', focusRingColor: '#8B5FBF' }}

                  >

                    <option value="">All Channels</option>

                    {channels.map(ch => (

                      <option key={ch.id} value={ch.id}>{ch.name}</option>

                    ))}

                  </select>

                </div>

              )}

              <div className="mt-6 space-y-3">

                {(() => {

                  const channelsToShow = selectedChannelForHistory

                    ? channels.filter(ch => ch.id === selectedChannelForHistory)

                    : channels;

                  const allVersions = channelsToShow.flatMap(ch =>

                    (ch.versions || []).map(v => ({ ...v, channelId: ch.id, channelName: ch.name }))

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

                          <span className="text-sm" style={{ color: '#8B5FBF' }}>{version.channelName}</span>

                        </div>

                        <div className="text-sm" style={{ color: '#D1D2D3' }}>

                          {formatTimeAgo(version.timestamp)} • {version.charsAdded.toLocaleString()} chars added

                        </div>

                      </div>

                      <button

                        onClick={() => handleRevertVersion(version.channelId, version.version)}

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

                  Default Character Threshold

                </label>

                <input

                  type="number"

                  value={defaultThreshold}

                  onChange={(e) => setDefaultThreshold(parseInt(e.target.value, 10) || 10000)}

                  min="1000"

                  step="1000"

                  className="rounded-lg px-4 py-2 text-white w-full focus:outline-none focus:ring-2"

                  style={{ backgroundColor: '#1D1C1D', borderColor: '#3F0E40', borderWidth: '1px', focusRingColor: '#8B5FBF' }}

                />

                <p className="text-sm mt-1" style={{ color: '#9CA3AF' }}>Number of characters before auto-update (applies to new channels)</p>

              </div>

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

                    Data is stored locally in your browser. When you connect to the backend, your User ID will be used to sync your channels.

                  </p>

                </div>

              </div>

            </div>

          </div>

        )}

      </main>



      {/* Add Channel Modal */}

      {showAddChannel && <AddChannelModal

        onClose={() => setShowAddChannel(false)}

        onAdd={handleAddChannel}

        defaultThreshold={defaultThreshold}

      />}

    </div>

  );

}

// Add Channel Modal Component
function AddChannelModal({ onClose, onAdd, defaultThreshold }) {
  const [formData, setFormData] = useState({
    channelName: '',
    docUrl: '',
    slackChannelId: '',
    threshold: defaultThreshold
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateForm = () => {
    const newErrors = {};
    if (!formData.channelName.trim()) {
      newErrors.channelName = 'Channel name is required';
    } else if (!formData.channelName.startsWith('#')) {
      newErrors.channelName = 'Channel name should start with #';
    }
    if (!formData.docUrl.trim()) {
      newErrors.docUrl = 'Google Doc URL is required';
    } else if (!formData.docUrl.includes('docs.google.com')) {
      newErrors.docUrl = 'Please enter a valid Google Docs URL';
    }
    if (formData.threshold < 1000) {
      newErrors.threshold = 'Threshold must be at least 1000 characters';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validateForm()) {
      setIsSubmitting(true);
      // Simulate API call
      setTimeout(() => {
        onAdd(formData);
        setIsSubmitting(false);
      }, 300);
    }
  };

  return (
    <div className="fixed inset-0 backdrop-blur-sm flex items-center justify-center p-4 z-50" style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)' }} onClick={onClose}>
      <div className="rounded-xl p-6 max-w-lg w-full border" style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-white">Add Slack Channel</h3>
          <button
            onClick={onClose}
            className="transition-colors hover:opacity-80"
            style={{ color: '#D1D2D3' }}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: '#D1D2D3' }}>
              Slack Channel Name <span style={{ color: '#E01E5A' }}>*</span>
            </label>
            <input
              type="text"
              placeholder="#channel-name"
              value={formData.channelName}
              onChange={(e) => setFormData({ ...formData, channelName: e.target.value })}
              className={`rounded-lg px-4 py-2 text-white w-full focus:outline-none focus:ring-2`}
              style={{ 
                backgroundColor: '#1D1C1D', 
                borderColor: errors.channelName ? '#E01E5A' : '#3F0E40', 
                borderWidth: '1px',
                focusRingColor: '#8B5FBF'
              }}
            />
            {errors.channelName && (
              <p className="text-sm mt-1" style={{ color: '#E01E5A' }}>{errors.channelName}</p>
            )}
            <p className="text-xs mt-1" style={{ color: '#9CA3AF' }}>The Slack channel name (e.g., #engineering-docs)</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: '#D1D2D3' }}>
              Google Doc URL <span style={{ color: '#E01E5A' }}>*</span>
            </label>
            <input
              type="url"
              placeholder="https://docs.google.com/document/d/..."
              value={formData.docUrl}
              onChange={(e) => setFormData({ ...formData, docUrl: e.target.value })}
              className={`rounded-lg px-4 py-2 text-white w-full focus:outline-none focus:ring-2`}
              style={{ 
                backgroundColor: '#1D1C1D', 
                borderColor: errors.docUrl ? '#E01E5A' : '#3F0E40', 
                borderWidth: '1px',
                focusRingColor: '#8B5FBF'
              }}
            />
            {errors.docUrl && (
              <p className="text-sm mt-1" style={{ color: '#E01E5A' }}>{errors.docUrl}</p>
            )}
            <p className="text-xs mt-1" style={{ color: '#9CA3AF' }}>The Google Doc that will be automatically updated</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: '#D1D2D3' }}>
              Character Threshold
            </label>
            <input
              type="number"
              value={formData.threshold}
              onChange={(e) => setFormData({ ...formData, threshold: parseInt(e.target.value, 10) || 10000 })}
              min="1000"
              step="1000"
              className={`rounded-lg px-4 py-2 text-white w-full focus:outline-none focus:ring-2`}
              style={{ 
                backgroundColor: '#1D1C1D', 
                borderColor: errors.threshold ? '#E01E5A' : '#3F0E40', 
                borderWidth: '1px',
                focusRingColor: '#8B5FBF'
              }}
            />
            {errors.threshold && (
              <p className="text-sm mt-1" style={{ color: '#E01E5A' }}>{errors.threshold}</p>
            )}
            <p className="text-xs mt-1" style={{ color: '#9CA3AF' }}>Number of characters before auto-update (default: {defaultThreshold.toLocaleString()})</p>
          </div>

          <div className="rounded-lg p-3 mt-4 border" style={{ backgroundColor: '#1D1C1D', borderColor: '#8B5FBF40' }}>
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: '#8B5FBF' }} />
              <div className="text-xs" style={{ color: '#8B5FBF' }}>
                <p className="font-medium mb-1">Integration Steps:</p>
                <ol className="list-decimal list-inside space-y-1" style={{ color: '#D1D2D3' }}>
                  <li>Add the Epimetheus bot to your Slack workspace</li>
                  <li>Invite the bot to the channel you want to track</li>
                  <li>Ensure the Google Doc is accessible to the bot</li>
                </ol>
              </div>
            </div>
          </div>

          <div className="flex gap-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 text-white px-4 py-2 rounded font-medium transition-colors border hover:opacity-80 disabled:opacity-50"
              style={{ backgroundColor: '#2C2C2C', borderColor: '#3F0E40' }}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 text-white px-4 py-2 rounded font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 hover:opacity-90"
              style={{ backgroundColor: '#611f69' }}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" />
                  Add Channel
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

