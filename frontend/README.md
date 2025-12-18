# Epimetheus Frontend

React-based admin dashboard for the Epimetheus Slack-to-Docs automation system.

## Features

- View all tracked documents
- Monitor message processing status
- Browse version history
- Revert to previous document versions
- Sync with Google Drive
- Search documents
- Manage document metadata

## Development

```bash
npm install
npm run dev
```

## Production (Docker)

Built and served via nginx in the Docker container. See parent directory's `docker-compose.yml`.

## Tech Stack

- React 19
- Vite
- TailwindCSS
- Lucide React Icons

