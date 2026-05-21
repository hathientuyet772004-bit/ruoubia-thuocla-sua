# Web Collector Tool Implementation Plan

A tool to help users quickly browse through pages and save them to the local `htmls/` folder with organized names.

## Backend (FastAPI)
- **Endpoint**: `GET /proxy?url=<URL>` - Fetches the page content using Playwright (to handle JS-heavy sites) or Requests.
- **Endpoint**: `POST /common/save` - Saves the fetched content to `htmls/` with a specific name and metadata.
- **Endpoint**: `GET /common/saved` - Lists already collected files in `htmls/`.

## Frontend (React/Vite)
- **UI Components**:
  - **URL Bar**: Modern, sleek input for the target site.
  - **Live Preview Pane**: Displays the page (handled via a proxy to bypass CORS).
  - **Saved Pages List**: Sidebar with thumbnails and metadata.
- **Stunning Design**:
  - Dark mode with neon accents.
  - Glassmorphic panels.
  - Smooth transitions.

## Implementation Steps:
1. Initialize FastAPI backend in `collector/backend`.
2. Initialize Vite/React frontend in `collector/frontend`.
3. Implement proxy and storage logic.
4. Craft the premium UI.
