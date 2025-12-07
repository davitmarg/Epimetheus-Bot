# Project Epimetheus: Slack-to-Docs RAG Bot

A system that automatically updates Google Docs based on Slack conversations, using RAG (Retrieval-Augmented Generation) to intelligently synthesize information.

## Architecture

### System Overview

```mermaid
graph TB
    subgraph "External Services"
        Slack[Slack Channels]
        GoogleDocs[Google Docs]
        OpenAI[OpenAI GPT-4]
    end
    
    subgraph "Epimetheus System"
        Bot[Bot Listener<br/>Slack Event Handler]
        Redis[(Redis<br/>Message Queue)]
        Updater[Updater Service<br/>Redis Consumer]
        API[API Service<br/>FastAPI]
        ChromaDB[(ChromaDB<br/>Vector Store)]
        MongoDB[(MongoDB<br/>Version Storage)]
    end
    
    Slack -->|Message Events| Bot
    Bot -->|Push Messages| Redis
    Redis -->|Consume Messages| Updater
    API -->|Query/Trigger| Updater
    Updater -->|Read Current Doc| GoogleDocs
    Updater -->|Store Chunks| ChromaDB
    Updater -->|Generate Update| OpenAI
    Updater -->|Save Version| MongoDB
    Updater -->|Write Updated Doc| GoogleDocs
    Updater -->|Query Context| ChromaDB
```

### Data Flow Diagram

```mermaid
sequenceDiagram
    participant Slack as Slack Channel
    participant Bot as Bot Listener
    participant Redis as Redis Buffer
    participant Updater as Updater Service
    participant ChromaDB as ChromaDB
    participant OpenAI as OpenAI GPT-4
    participant GoogleDocs as Google Docs
    participant MongoDB as MongoDB<br/>Version Storage
    
    Slack->>Bot: New Message Event
    Bot->>Bot: Filter Bot Messages
    Bot->>Redis: Push Message to Queue<br/>(epimetheus:updater_queue)
    Redis->>Updater: Consume Message<br/>(Blocking Pop)
    Updater->>Updater: Determine Target Document<br/>(Vector Search)
    Updater->>GoogleDocs: Read Current Document
    GoogleDocs-->>Updater: Document Content
    Updater->>Updater: Prepare Context<br/>(Old Doc + New Message)
    Updater->>OpenAI: Generate Updated Document
    OpenAI-->>Updater: New Document Content
    Updater->>MongoDB: Save Version<br/>(Old Content + Metadata)
    Updater->>GoogleDocs: Update Document<br/>(New Content)
    Updater->>ChromaDB: Store Document Chunks<br/>(For RAG)
    Updater->>Slack: Send Update Notification<br/>(Optional)
    
    Note over Updater,MongoDB: Manual Operations Available:<br/>- Trigger Update<br/>- List Versions<br/>- Revert to Version
```

### Component Interaction Diagram

```mermaid
graph LR
    subgraph "Input Layer"
        A[Slack Messages]
    end
    
    subgraph "Processing Layer"
        B[Bot Listener]
        C[Redis Buffer]
        D[Updater Service]
    end
    
    subgraph "Storage Layer"
        E[ChromaDB<br/>Vector Store]
        F[MongoDB<br/>Version Storage]
    end
    
    subgraph "External APIs"
        G[OpenAI GPT-4]
        H[Google Docs API]
    end
    
    A -->|Event Stream| B
    B -->|Immediate Dispatch| C
    C -->|Message Queue| D
    D -->|Store Chunks| E
    D -->|Save Versions| F
    D -->|Generate Content| G
    D -->|Read/Write| H
    D -->|Query Context| E
```

### Component Architecture

The system consists of four main services and a repository layer:

#### Services (with run functions)

**1. Bot Service** (`services/bot_service.py`)
- Unified service handling both regular messages and app mentions
- **Message Handling**: Listens to all Slack message events, filters bot messages, buffers messages by thread and dispatches to Redis queue when batch size is reached
- **App Mentions**: Handles direct mentions (`@Epimetheus`) using agentic repository for intelligent responses
- Uses Redis-based message buffering system (`MessageBuffer`) for async processing
- Processes mentions with LangChain-based agent for Q&A and document updates
- Replies directly to users in Slack threads with loading/success/error reactions
- Falls back to checking message text for bot mentions if app_mention events don't fire

**2. Updater Service** (`services/updater_service.py`)
- Consumes messages from Redis queue for async/batched processing
- **Knowledge Extraction**: Extracts knowledge from message chunks and determines if documents need updating
- Determines target document(s) using vector search (ChromaDB)
- Generates updated document versions using OpenAI GPT-4 via LLM Repository
- Intelligently merges new information with existing document content using partial updates (preserves formatting)
- Maintains version history with revert capability
- Stores document chunks in ChromaDB for RAG context
- Sends Slack notifications when documents are updated
- Supports direct function calls for immediate processing (from agent tools)
- Processes messages as a log: chunks messages → extracts knowledge → checks if update needed → processes update or flushes

**3. API Service** (`services/api_service.py`)
- Provides REST API endpoints for managing documents
- Allows manual triggering of updates (verification)
- Enables version management and reverting
- Provides status and health check endpoints
- Manages Drive folder mapping synchronization

#### Repository Layer (data access)

**Drive Repository** (`repository/drive_repository.py`)
- Google Drive API operations
- Document CRUD operations
- Content reading and writing

**Document Repository** (`repository/document_repository.py`)
- MongoDB operations for document versions
- Document metadata management
- Drive file mapping storage
- Convenience methods combining Drive and MongoDB operations
- Search across Drive and metadata
- Folder synchronization
- Vector search operations for RAG

**LLM Repository** (`repository/llm_repository/`)
- Centralized LLM operations using LangChain
- Prompt management via `prompts.py` module
- Document update generation
- Change summary generation
- Question answering with RAG
- Intent classification
- Knowledge extraction from conversations
- Supports OpenAI and OpenAI-compatible APIs (e.g., OpenRouter)
- **Agent System** (`agentic.py`): EpimetheusAgent class for processing user messages with LangChain tools
- **Agent Tools**: LangChain tools defined in `agentic.py`:
  - `answer_question_from_documentation`: Answers questions using RAG
  - `update_documentation_with_information`: Updates documents with new information
  - `get_document_count`: Returns document count
  - `list_all_documents`: Lists all documents with links
  - `get_document_last_updated`: Checks document update times
  - `update_document_formatting`: Updates document formatting without changing content
  - `update_document_partial`: Performs partial updates to specific sections
- **Agentic Repository** (`agentic.py`): Processes Slack mention commands, extracts document mentions, uses vector search for document routing, and coordinates agent responses

## Quick Start with Docker Compose

The easiest way to run the entire system is using Docker Compose:

### Prerequisites
- Docker and Docker Compose installed
- Google Cloud service account JSON credentials file
- Slack bot tokens
- OpenAI API key

### Creating Required Accounts

#### 1. Google Cloud Service Account Setup

To interact with Google Docs and Drive, you need to create a service account:

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Click "Select a project" → "New Project"
   - Enter a project name (e.g., "Epimetheus-Bot")
   - Click "Create"

2. **Enable Required APIs:**
   - Navigate to "APIs & Services" → "Library"
   - Search for "Google Docs API" and click "Enable"
   - Search for "Google Drive API" and click "Enable"

3. **Create a Service Account:**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "Service Account"
   - Enter a name (e.g., "epimetheus-bot")
   - Click "Create and Continue"
   - Skip role assignment (click "Continue")
   - Click "Done"

4. **Create and Download Service Account Key:**
   - Click on the newly created service account
   - Go to the "Keys" tab
   - Click "Add Key" → "Create new key"
   - Select "JSON" format
   - Click "Create" (this downloads the JSON file)
   - Save this file as `credentials.json` in your project root

5. **Share Google Drive Folder with Service Account:**
   - Open Google Drive and navigate to the folder you want to use
   - Right-click the folder → "Share"
   - Add the service account email (found in the JSON file as `client_email`)
   - Give it "Editor" permissions
   - Click "Send"

6. **Get Your Drive Folder ID:**
   - Open the Google Drive folder in your browser
   - The folder ID is in the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
   - Copy this ID and use it for `GOOGLE_DRIVE_FOLDER_ID` in your `.env` file

#### 2. Slack App Setup

To create a Slack bot that listens to messages, follow these detailed steps:

##### Step 1: Create a Slack App

1. **Navigate to Slack API:**
   - Go to [https://api.slack.com/apps](https://api.slack.com/apps)
   - Sign in with your Slack workspace credentials

2. **Create New App:**
   - Click the **"Create New App"** button
   - Select **"From scratch"** (not "From an app manifest")
   - Enter an app name (e.g., "Epimetheus Bot")
   - Select your workspace from the dropdown
   - Click **"Create App"**

   📖 **Reference:** [Creating a Slack App](https://api.slack.com/authentication/basics)

##### Step 2: Configure Bot Permissions (Scopes)

The bot needs specific permissions to read messages from channels. Here's how to configure them:

1. **Navigate to OAuth & Permissions:**
   - In the left sidebar of your app settings, click **"OAuth & Permissions"**
   - Scroll down to the **"Scopes"** section
   - Find the **"Bot Token Scopes"** subsection

2. **Add Required Scopes:**
   Click **"Add an OAuth Scope"** and add each of the following scopes:

   **Required Scopes:**
   - `app_mentions:read` - Read app mentions
     - *Required for the bot to receive mention events*
   - `chat:write` - Send messages
     - *Required for the bot to reply to mentions*
   - `reactions:write` - Add/remove reactions
     - *Required for loading indicators (⏳ → ✅)*
   - `channels:history` - Read channel message history
     - *Required to read message context for processing*
   - `channels:read` - View basic channel information
     - *Required to access channel details*
   - `groups:history` - Read private channel message history
     - *Required for private channel support*
   - `groups:read` - View basic private channel information
     - *Required for private channel support*
   - `mpim:history` - Read group DM message history
     - *Required for group DM support*
   - `mpim:read` - View basic group DM information
     - *Required for group DM support*

   **Optional Scopes:**
   - `im:history` - Read direct message history (if you want DM support)
   - `im:read` - View direct message information (if you want DM support)

   📖 **Reference:** [Slack OAuth Scopes](https://api.slack.com/scopes)

##### Step 3: Enable Socket Mode

Socket Mode allows your bot to receive events without exposing a public HTTP endpoint. This is required for Epimetheus Bot.

1. **Navigate to Socket Mode:**
   - In the left sidebar, click **"Socket Mode"**
   - Toggle the **"Enable Socket Mode"** switch to **ON**

2. **Create App-Level Token:**
   - Scroll down to the **"App-Level Tokens"** section
   - Click **"Create Token"** or **"Generate New Token"**
   - Enter a name for the token (e.g., "Epimetheus Socket Token")
   - Under **"Scopes"**, select: `connections:write`
   - Click **"Generate"**

3. **Copy the Token:**
   - **Important:** Copy the token immediately - you won't be able to see it again!
   - This token starts with `xapp-` and is your `SLACK_APP_TOKEN`
   - Store it securely - you'll add it to your `.env` file

   📖 **Reference:** [Using Socket Mode](https://api.slack.com/apis/connections/socket)

##### Step 4: Install App to Workspace

After configuring permissions, you need to install the app to your workspace:

1. **Navigate to OAuth & Permissions:**
   - Go back to **"OAuth & Permissions"** in the left sidebar
   - Scroll to the top of the page

2. **Install to Workspace:**
   - Click the **"Install to Workspace"** button (or **"Reinstall to Workspace"** if updating)
   - Review the permission scopes that will be granted
   - Click **"Allow"** to authorize the app

3. **Copy Bot Token:**
   - After installation, you'll see **"Bot User OAuth Token"** at the top of the page
   - Click **"Copy"** to copy the token
   - This token starts with `xoxb-` and is your `SLACK_BOT_TOKEN`
   - Store it securely - you'll add it to your `.env` file

   📖 **Reference:** [Installing Apps](https://api.slack.com/authentication/oauth-v2)

##### Step 5: Invite Bot to Channels

The bot needs to be invited to channels to receive message events:

1. **For Public Channels:**
   - Open the Slack channel where you want the bot to listen
   - Type: `/invite @Epimetheus Bot` (replace with your bot's name)
   - Press Enter
   - The bot will be added to the channel

2. **For Private Channels:**
   - Open the private channel
   - Click the channel name at the top
   - Go to the **"Integrations"** tab
   - Click **"Add apps"**
   - Search for your bot and add it

3. **Verify Bot is Active:**
   - You should see a message in the channel indicating the bot joined
   - The bot will now receive all message events from that channel

   📖 **Reference:** [Inviting Apps to Channels](https://slack.com/help/articles/201398467-Guide-to-apps)

##### Step 6: Add Tokens to Environment

Add both tokens to your `.env` file:

```bash
# Slack Bot Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
```

**Security Notes:**
- Never commit these tokens to version control
- Keep tokens secure and rotate them if compromised
- Use different tokens for development and production environments

##### Troubleshooting

**Bot not receiving messages?**
- Verify the bot is invited to the channel
- Check that Socket Mode is enabled
- Ensure all required scopes are added
- Verify tokens are correct in your `.env` file

**Permission errors?**
- Reinstall the app to workspace after adding new scopes
- Check that you've added all required scopes listed above
- Verify the bot user has access to the channels

**Connection issues?**
- Verify `SLACK_APP_TOKEN` starts with `xapp-`
- Verify `SLACK_BOT_TOKEN` starts with `xoxb-`
- Check that Socket Mode is enabled in app settings

📖 **Additional Resources:**
- [Slack API Documentation](https://api.slack.com/)
- [Slack Events API](https://api.slack.com/events-api)
- [Socket Mode Guide](https://api.slack.com/apis/connections/socket)
- [Troubleshooting Slack Apps](https://api.slack.com/events-api#troubleshooting)

### Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd Epimetheus-Bot
```

2. **Create environment file:**
```bash
cp .env-example .env
# Edit .env with your credentials
```

3. **Place your Google credentials file:**
```bash
# Copy your Google service account JSON file to the project root
cp /path/to/your/credentials.json ./credentials.json
```

4. **Start all services:**
```bash
docker-compose up -d
```

This will start:
- **Redis** (port 6379) - Message queue
- **ChromaDB** (port 8001) - Vector database
- **MongoDB** (port 27017) - Version storage
- **Epimetheus App** (port 8000) - Main application (Bot + Updater Service + API Service)

**Note:** The API service automatically syncs the Google Drive folder mapping on startup. You'll see a log message indicating how many documents were found.

By default, all services run together. You can also run them separately:
- `python main.py bot` - Run only the Slack bot
- `python main.py updater` - Run only the updater service (Redis consumer)
- `python main.py api` - Run only the API service

5. **View logs:**
```bash
docker-compose logs -f app
```

6. **Stop services:**
```bash
docker-compose down
```

## Manual Setup (Without Docker)

### Prerequisites
- Python 3.11+
- Redis server
- Google Cloud project with Docs API enabled
- OpenAI API key

> **Note:** For detailed instructions on creating a Google Cloud service account and Slack app, see the [Creating Required Accounts](#creating-required-accounts) section above.

### Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set up environment variables:**
```bash
cp .env-example .env
# Edit .env with your credentials
```

3. **Set up Google Cloud credentials:**
   - Follow the [Google Cloud Service Account Setup](#1-google-cloud-service-account-setup) instructions above
   - Place the downloaded JSON file in your project root as `credentials.json`
   - Set `GOOGLE_CREDENTIALS_PATH=./credentials.json` in `.env`

4. **Set up Slack bot:**
   - Follow the [Slack App Setup](#2-slack-app-setup) instructions above
   - Add `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` to your `.env` file

5. **Configure your Google Drive folder:**
   - Create a Google Drive folder for your documents
   - Share it with your service account email (from the JSON file)
   - Copy the folder ID from the URL (the long string after `/folders/`)
   - Set `GOOGLE_DRIVE_FOLDER_ID` in `.env`
   - **Note:** The Drive folder mapping is automatically synced on startup. You can also manually sync using: `POST /api/v1/drive/mapping/sync`

6. **Start Redis:**
```bash
redis-server
```

7. **Start ChromaDB (optional, for Docker setup):**
```bash
docker run -d -p 8001:8000 chromadb/chroma:latest
```

8. **Run the application:**
```bash
# Run all services together
python main.py

# Or run services separately:
python main.py bot      # Run only the Slack bot
python main.py updater  # Run only the updater service (Redis consumer)
python main.py api      # Run only the API service
```

By default, running `python main.py` starts all three services:
- Slack bot listener (background thread)
- Updater service - Redis consumer (background thread)
- API service - FastAPI server (main thread, port 8000)

## Key Features

### Knowledge Extraction System

The bot automatically extracts knowledge from Slack conversations:

- **Message Chunking**: Analyzes the last N messages (configurable via `MESSAGE_CHUNK_SIZE`)
- **Knowledge Extraction**: Uses LLM to identify key facts, updates, and information worth documenting
- **Relevance Scoring**: Calculates confidence scores to determine if documents need updating
- **Automatic Updates**: Triggers document updates when new knowledge is detected

### LangChain Agent System

The bot includes a sophisticated agent system for handling direct mentions:

- **Question Answering**: Answers questions about existing documentation using RAG
- **Document Updates**: Updates documentation when users provide new information
- **Document Management**: Lists documents, checks update times, gets document counts
- **Formatting Tools**: Updates document formatting or performs partial section updates
- **Tool-Based Architecture**: Uses LangChain tools for structured operations:
  - `answer_question_from_documentation`: RAG-based Q&A with document links
  - `update_documentation_with_information`: Document updates with change summaries
  - `get_document_count`: Returns count of documents in the system
  - `list_all_documents`: Lists all documents with names and Google Docs links
  - `get_document_last_updated`: Checks when documents were last modified
  - `update_document_formatting`: Updates formatting (headings, bold, italic, lists) without changing content
  - `update_document_partial`: Performs partial updates to specific sections (preserves formatting and enables versioning)
- **Context-Aware**: Maintains conversation context and provides relevant document links
- **Automatic Routing**: Uses vector search to find relevant documents when not explicitly mentioned
- **Error Handling**: Graceful error handling with informative error messages
- **Reaction Feedback**: Visual feedback with loading (⏳), success (✅), and error (❌) reactions

### LLM Repository & Prompt Management

Centralized LLM operations with clean prompt management:

- **Unified Interface**: Single repository for all LLM operations
- **Prompt Centralization**: All prompts managed in `repository/llm_repository/prompts.py`
- **Flexible Backend**: Supports OpenAI and OpenAI-compatible APIs (e.g., OpenRouter)
- **Consistent Patterns**: Standardized prompt templates for document updates, Q&A, summaries, and knowledge extraction
- **No Redundancy**: All LLM operations go through the repository, eliminating duplicate LLM instance creation

## API Endpoints

The API Service exposes the following endpoints:

### Document Management
- `GET /api/v1/documents` - List all documents in Drive folder
- `GET /api/v1/documents/search` - Search documents by name or metadata
- `POST /api/v1/documents` - Create a new document
- `GET /api/v1/documents/{doc_id}` - Get document content and metadata
- `GET /api/v1/documents/{doc_id}/metadata` - Get document metadata
- `PUT /api/v1/documents/{doc_id}/metadata` - Update document metadata
- `GET /api/v1/documents/metadata/all` - Get metadata for all documents

### Drive Mapping
- `GET /api/v1/drive/mapping` - Get current Drive file mapping from MongoDB
- `POST /api/v1/drive/mapping/sync` - Manually sync Drive folder contents to MongoDB mapping (automatically synced on startup)
- `PUT /api/v1/drive/mapping` - Manually update the Drive file mapping

### Document Versions
- `POST /api/v1/trigger` - Verify document exists (documents are updated automatically when messages are received)
- `GET /api/v1/versions/{doc_id}` - List all document versions
- `GET /api/v1/versions/{doc_id}/{version_id}` - Get specific version
- `POST /api/v1/revert/{doc_id}/{version_id}` - Revert to previous version
- `GET /api/v1/status` - Get service status information
- `GET /health` - Health check endpoint

## How It Works

### Automatic Knowledge Extraction Flow

1. **Message Ingestion**: The Bot listens to Slack channels and receives message events in real-time.

2. **Knowledge Extraction**: For each message:
   - Retrieves the last N messages from the channel (configurable via `MESSAGE_CHUNK_SIZE`)
   - Chunks messages into groups for analysis
   - Uses LLM to extract knowledge from message chunks
   - Determines if extracted knowledge contains new information worth documenting

3. **Document Routing**: If new knowledge is detected:
   - Uses vector similarity search in ChromaDB to find relevant documents
   - Calculates confidence scores based on relevance
   - Routes to the most relevant document(s)

4. **Document Update**: The system:
   - Reads the current document content from Google Docs
   - Prepares context combining the existing document and new messages
   - Uses OpenAI GPT-4 (via LLM Repository) to generate an updated document that:
     - Preserves existing valuable information
     - Integrates new information from Slack conversations
     - Maintains proper formatting and structure
     - Removes outdated information when appropriate

5. **Versioning**: Each update creates a new version stored in MongoDB that can be reverted if needed.

6. **Vector Storage**: Updated document chunks are stored in ChromaDB for future RAG queries and document routing.

### Direct Mention Flow (Agent-Based)

1. **App Mention**: When the bot is directly mentioned (`@Epimetheus`):
   - Extracts the message text (removing bot mention)
   - Attempts to extract document ID from message (Google Docs URLs)
   - If no document ID found, uses vector search to find relevant document

2. **Agent Processing**: The LangChain agent:
   - Classifies user intent (question vs. update)
   - Uses appropriate tools:
     - `answer_question_from_documentation`: Answers questions using RAG
     - `update_documentation_with_information`: Updates documents with new information
   - Processes tool calls and generates responses

3. **Response**: The agent responds directly in the Slack thread with:
   - Answers to questions (with document links)
   - Confirmation of document updates (with summaries and links)

### Redis Queue-Based Flow (Log-Based Processing)

The system uses Redis queue for log-based knowledge extraction:
- Messages are buffered by thread and pushed to Redis queue (`epimetheus:updater_queue`) via `MessageBuffer` when batch size is reached
- Updater Service continuously consumes from queue (blocking pop, one at a time)
- **Log-Based Processing**: Messages are processed as a log:
  1. Chunks messages (last N messages, configurable via `MESSAGE_CHUNK_SIZE`)
  2. Extracts knowledge from chunks using LLM
  3. Checks if document needs update based on relevance threshold
  4. If update needed: processes update
  5. If not needed: flushes and continues
- Provides async/batched processing capability
- **Dual Processing**: Updater Service supports BOTH direct calls (for immediate agent tool execution) and Redis queue consumption (for log-based knowledge extraction) simultaneously

## Configuration

Key environment variables:

- `SLACK_BOT_TOKEN`: Slack bot token (required)
- `SLACK_APP_TOKEN`: Slack app token (required)
- `GOOGLE_DRIVE_FOLDER_ID`: Google Drive folder ID containing documents (required)
- `GOOGLE_CREDENTIALS_PATH`: Path to Google service account JSON file (required)
- `OPENAI_API_KEY`: OpenAI API key for GPT-4 (required)
- `OPENAI_BASE_URL`: Optional base URL for OpenAI-compatible APIs (e.g., OpenRouter: `https://openrouter.ai/api/v1`)
- `OPENAI_MODEL`: Model to use (default: `gpt-4`)
- `MESSAGE_CHUNK_SIZE`: Number of recent messages to analyze for knowledge extraction (default: `10`)
- `KNOWLEDGE_EXTRACTION_THRESHOLD`: Relevance threshold for knowledge extraction (default: `0.7`)
- `CHROMA_DB_PATH`: Path for ChromaDB storage (default: `./chroma_db`)
- `CHROMA_HOST`: ChromaDB host (default: `localhost`, use `chromadb` in Docker)
- `CHROMA_PORT`: ChromaDB port (default: 8000)
- `CHROMA_USE_HTTP`: Use HTTP client for ChromaDB (set to `true` in Docker)
- `MONGODB_HOST`: MongoDB host (default: `localhost`, use `mongodb` in Docker)
- `MONGODB_PORT`: MongoDB port (default: 27017)
- `MONGODB_DATABASE`: MongoDB database name (default: `epimetheus`)
- `MONGODB_USERNAME`: MongoDB username (optional, leave empty for no authentication)
- `MONGODB_PASSWORD`: MongoDB password (optional, leave empty for no authentication)
- `REDIS_HOST`: Redis host (default: `localhost`, use `redis` in Docker)
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)

## Usage Examples

### Using the Bot in Slack

#### Automatic Knowledge Extraction

The bot automatically monitors channels and extracts knowledge:

1. **Normal Conversation**: Just chat in channels where the bot is present
   - The bot analyzes the last N messages (default: 10)
   - Extracts knowledge and updates relevant documents automatically
   - No action required from users

2. **Example Conversation**:
   ```
   User A: "We've updated our deployment process. Now we use Docker Compose."
   User B: "Yes, and we've added health checks to all services."
   ```
   The bot will:
   - Extract knowledge about the deployment process update
   - Find relevant documentation using vector search
   - Update the documentation automatically

#### Direct Mentions (Agent Mode)

Mention the bot directly (`@Epimetheus`) for interactive Q&A or updates:

1. **Asking Questions**:
   ```
   @Epimetheus What's our deployment process?
   ```
   The bot will:
   - Search documentation using RAG
   - Provide an answer with relevant document links
   - Respond in the thread

2. **Providing Updates**:
   ```
   @Epimetheus We've changed our API endpoint to /api/v2
   ```
   The bot will:
   - Determine which document to update
   - Update the documentation
   - Confirm with a summary and document link

3. **Mentioning Specific Documents**:
   ```
   @Epimetheus Update https://docs.google.com/document/d/DOC_ID with: New feature added
   ```
   The bot will:
   - Extract the document ID from the URL
   - Update that specific document
   - Confirm the update

4. **Listing Documents**:
   ```
   @Epimetheus List all documents
   ```
   The bot will:
   - List all documents with names and links
   - Show document count

5. **Checking Update Times**:
   ```
   @Epimetheus When was the last document updated?
   ```
   The bot will:
   - Check last modified times for documents
   - Show documents sorted by update time

6. **Formatting Documents**:
   ```
   @Epimetheus Format the deployment document with proper headings
   ```
   The bot will:
   - Update document formatting without changing content
   - Apply requested formatting improvements

7. **Partial Updates**:
   ```
   @Epimetheus Update the API section with: New endpoint added
   ```
   The bot will:
   - Update only the specified section
   - Preserve formatting and enable versioning

## Manual Operations

### Sync Drive Folder Mapping
The Drive folder mapping is automatically synced when the API service starts. You can also manually trigger a sync:
```bash
curl -X POST http://localhost:8000/api/v1/drive/mapping/sync
```

### Verify Document Exists
```bash
curl -X POST http://localhost:8000/api/v1/trigger \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "your-doc-id"}'
```
Note: Documents are automatically updated when messages are received. This endpoint only verifies that a document exists.

### List Documents
```bash
curl http://localhost:8000/api/v1/documents
```

### Search Documents
```bash
curl "http://localhost:8000/api/v1/documents/search?query=your-search-term"
```

### List Versions
```bash
curl http://localhost:8000/api/v1/versions/your-doc-id
```

### Revert to Version
```bash
curl -X POST http://localhost:8000/api/v1/revert/your-doc-id/version-id
```

## Docker Volumes

The Docker Compose setup creates persistent volumes for:
- `redis_data` - Redis persistence
- `chromadb_data` - ChromaDB data
- `mongodb_data` - MongoDB data (version storage)
- Local directories mounted for:
  - `./chroma_db` - ChromaDB local storage (if not using HTTP client)
  - `./credentials.json` - Google service account credentials (read-only)

## Project Structure

```
Epimetheus-Bot/
├── services/                    # Services with run functions
│   ├── bot_service.py           # Unified Slack bot (messages + mentions)
│   ├── updater_service.py       # Document updater (Redis consumer + knowledge extraction)
│   └── api_service.py           # FastAPI REST API
├── repository/                  # Data access layer
│   ├── drive_repository.py      # Google Drive operations
│   ├── document_repository.py   # MongoDB operations + convenience methods
│   ├── slack_repository.py      # Slack API operations
│   └── llm_repository/          # LLM operations with LangChain
│       ├── __init__.py          # LLM Repository implementation
│       ├── agentic.py           # Agent system, tools, and agentic repository
│       └── prompts.py           # Centralized prompt management
├── utils/                       # Shared utilities
│   ├── db_utils.py              # Database connections (Redis, MongoDB, ChromaDB)
│   ├── message_utils.py         # Message formatting utilities and document ID extraction helpers
│   └── constants.py             # Constants and default messages
├── main.py                      # Application entry point
├── requirements.txt             # Python dependencies
├── docker-compose.yml           # Docker Compose configuration
├── Dockerfile                   # Docker image definition
├── pytest.ini                   # Pytest configuration
├── .env-example                 # Environment variables template
├── tests/                       # Test suite (if exists)
│   ├── __init__.py              # Test package
│   ├── conftest.py              # Pytest fixtures
│   └── test_e2e.py              # End-to-end tests
└── README.md                    # This file
```

## Notes

- **Architecture**: Clean separation between services (business logic) and repositories (data access)
- **Multiple Documents**: Supports multiple dynamic documents in a Google Drive folder
- **Drive Mapping**: File mapping stored in MongoDB (`drive_file_mapping` collection) for fast access
- **Auto-Sync**: Drive folder mapping is automatically synced on API service startup. Manual sync available via `POST /api/v1/drive/mapping/sync`
- **Versioning**: Version history stored in MongoDB for scalability and querying
- **Vector Search**: ChromaDB used for content-based document routing and RAG queries
- **ChromaDB**: Can be used as persistent local client or via HTTP (recommended for Docker)
- **Message Filtering**: Bot ignores its own messages to prevent loops
- **Knowledge Extraction**: Automatically extracts knowledge from message chunks and determines if documents need updating using LLM-based extraction
- **Agent System**: LangChain-based agent handles direct mentions with 7 tools for Q&A, document updates, listing, formatting, and partial updates
- **LLM Repository**: Centralized LLM operations with LangChain and prompt management
- **Prompt Management**: All prompts centralized in `repository/llm_repository/prompts.py` for easy maintenance
- **Log-Based Processing**: Messages processed as a log: chunk → extract knowledge → check relevance → update or flush
- **Dual Processing**: Updater Service supports BOTH direct calls (for agent tools) and Redis queue consumption (for log-based extraction) simultaneously
- **Scalability**: Services can run together in a single process or separately (bot, updater, api)
- **Message Buffering**: `MessageBuffer` class buffers messages by thread and dispatches to Redis when batch size reached
- **Document Routing**: Messages automatically routed to documents using vector similarity search (ChromaDB)
- **Slack Notifications**: Notifications sent to Slack threads when documents are updated (with change summaries)
- **Direct Mentions**: Bot responds to direct mentions (`@Epimetheus`) with agent-based Q&A or document updates, with loading/success/error reactions
- **Fallback Mention Detection**: Checks message text for bot mentions if app_mention events don't fire
- **Version History**: Complete version history stored in MongoDB with revert capability
- **Vector Storage**: Document chunks stored in ChromaDB for RAG queries and document routing

## Testing

The project includes end-to-end tests that verify the complete message processing flow from Slack message ingestion to document updates.

### Running Tests

1. **Install test dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run all tests:**
```bash
pytest tests/
```

3. **Run with verbose output:**
```bash
pytest tests/ -v
```

4. **Run a specific test file:**
```bash
pytest tests/test_e2e.py
```

5. **Run with coverage:**
```bash
pytest tests/ --cov=. --cov-report=html
```

### Test Structure

```
tests/
├── __init__.py          # Test package initialization
├── conftest.py          # Pytest fixtures and configuration
└── test_e2e.py          # End-to-end tests
```

### Test Coverage

The end-to-end tests (`test_e2e.py`) cover:

1. **Complete Message Flow**: Tests the full pipeline from message ingestion → queueing → consumption → document update
2. **Document Routing**: Verifies messages are correctly routed to documents using vector search
3. **Fallback Routing**: Tests fallback behavior when vector search is unavailable
4. **Multi-Thread Processing**: Ensures messages from multiple threads are processed correctly
5. **Manual Trigger**: Tests manual document update triggering

### Test Fixtures

The test suite uses pytest fixtures (defined in `conftest.py`) to mock:
- Redis client and operations
- MongoDB database and collections
- ChromaDB vector database
- OpenAI API client
- Google Drive and Docs APIs
- Environment variables

### Writing New Tests

To add new tests:

1. Create test functions in `tests/test_e2e.py` or create new test files
2. Use the provided fixtures for mocking external services
3. Follow the existing test patterns for consistency
4. Ensure tests are isolated and don't depend on external services

Example test structure:
```python
def test_new_feature(mock_env_vars, mock_redis_client):
    """Test description"""
    # Test implementation
    assert expected_result == actual_result
```

## Troubleshooting

### Docker Issues
- Ensure ports 6379, 8000, and 8001 are not already in use
- Check logs: `docker-compose logs -f`
- Verify environment variables: `docker-compose config`

### ChromaDB Connection
- If using Docker, ensure `CHROMA_USE_HTTP=true` is set
- Check ChromaDB health: `curl http://localhost:8001/api/v1/heartbeat`

### Redis Connection
- Verify Redis is running: `redis-cli ping`
- Check Redis logs in Docker: `docker-compose logs redis`
