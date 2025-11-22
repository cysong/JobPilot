# JobPilot Frontend

AI-powered job application assistant - Frontend Application

## Tech Stack

- **Framework**: React 18 + Vite 5
- **Language**: TypeScript 5.x
- **UI**: Tailwind CSS
- **State Management**: Zustand
- **Routing**: React Router v6
- **HTTP Client**: Axios + TanStack Query (React Query)
- **Date Utilities**: date-fns

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your backend API URL
# Default: http://localhost:8000/api/v1
```

### 3. Run Development Server

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

## Project Structure

```
frontend/
├── src/
│   ├── api/                # API client and endpoint definitions
│   ├── components/         # Reusable UI components
│   │   └── ui/            # Base UI components
│   ├── features/          # Feature modules (auth, jobs, resumes, applications)
│   ├── hooks/             # Custom React hooks
│   ├── store/             # Zustand state management
│   ├── types/             # TypeScript type definitions
│   ├── utils/             # Utility functions
│   ├── App.tsx            # Main application component
│   └── main.tsx           # Application entry point
├── public/                # Static assets
└── index.html             # HTML template
```

## Development

### Code Formatting

```bash
npm run lint
```

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Environment Variables

- `VITE_API_BASE_URL`: Backend API base URL

## Version

Current version: **0.1.0**
