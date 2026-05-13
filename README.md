# 🤖 Job Finder AI

<div align="center">

![Job Finder AI Banner](https://img.shields.io/badge/Job%20Finder-AI%20Powered-6366f1?style=for-the-badge&logo=sparkles&logoColor=white)

**An AI-powered full-stack job matching platform that analyzes your resume, finds the best-fit jobs, and prepares you for interviews — all in one place.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-black?style=for-the-badge&logo=vercel)](https://job-finder-ai.vercel.app)
[![Backend API](https://img.shields.io/badge/Backend%20API-Render-46E3B7?style=for-the-badge&logo=render)](https://job-finder-ai-backend.onrender.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [System Architecture](#-system-architecture)
- [Project Structure](#-project-structure)
- [Getting Started (Local Development)](#-getting-started-local-development)
- [Environment Variables](#-environment-variables)
- [Deployment](#-deployment)
- [API Endpoints](#-api-endpoints)
- [Database Schema](#-database-schema)
- [Job Data Sources](#-job-data-sources)

---

## 🌟 Overview

Job Finder AI is a modern, full-stack job search platform built with **Next.js** (frontend) and **FastAPI** (backend). It aggregates real-time job listings from multiple sources, parses your PDF resume using AI, and then uses **Google Gemini** to provide:

- **AI-powered job matching** based on your skills and experience
- **ATS Score** — how well your resume matches a specific job description
- **AI Cover Letter Generator** — personalized for each job
- **Skills Gap Analysis** — what skills you're missing vs what the job requires
- **Interview Prep** — AI-generated questions tailored to the role
- **Resume Improvement Suggestions** — 5 actionable improvements from Gemini AI
- **Application Tracker** — Kanban board to track your job applications

---

## ✨ Features

### 🔍 Smart Job Search
- Real-time job aggregation from **4+ job sources** (RemoteOK, Remotive, Adzuna, JSearch)
- Filter by location, job type, source, and keywords
- Auto-refreshing job cache with 6-hour scheduler

### 📄 Resume Intelligence
- **PDF resume upload** and AI parsing via Google Gemini
- Automatic skills and experience extraction
- Resume stored in Supabase and linked to your profile
- **"Improve My Resume"** — 5 specific, actionable improvements

### 🤖 AI Co-Pilot (per job)
- **ATS Score** — Compatibility percentage with a job description
- **Cover Letter** — One-click personalized cover letter generation
- **Skills Gap Analysis** — Side-by-side user vs job skills comparison
- **Interview Prep** — Role-specific technical and behavioral questions

### 📊 Application Tracker
- **Kanban board** with 5 columns: Saved → Applied → Interview → Offer → Rejected
- **Drag & drop** cards between columns (`@hello-pangea/dnd`)
- Stats bar: total applied, interviews, offers
- Persisted in Supabase with real-time updates

### 🎨 UI/UX
- **Dark mode enforced** — premium dark glassmorphism design
- **Fully responsive** — mobile, tablet, desktop
- Hamburger menu on mobile
- Toast notifications (Sonner)
- Loading skeletons on all data-fetching views
- Smooth hover animations and gradient effects

### 🔐 Authentication
- **Google OAuth** via Supabase Auth
- Row-Level Security (RLS) — each user only sees their own data
- `AuthGuard` component protects all private routes

---

## 🛠️ Tech Stack

### Frontend
| Technology | Purpose |
|---|---|
| **Next.js 15** (App Router) | React framework |
| **TypeScript** | Type safety |
| **Tailwind CSS v4** | Styling |
| **next-themes** | Dark mode |
| **@hello-pangea/dnd** | Drag & drop Kanban |
| **Sonner** | Toast notifications |
| **Axios** | HTTP client |
| **Lucide React** | Icons |
| **shadcn/ui** | UI components |

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI** | Python API framework |
| **Google Gemini AI** (`gemini-2.5-flash`) | AI features |
| **Supabase** (PostgreSQL) | Database + Auth |
| **APScheduler** | Job cache refresh scheduler |
| **httpx** | Async HTTP client |
| **python-multipart** | PDF file upload handling |
| **Pydantic** | Data validation |
| **uvicorn** | ASGI server |

### Infrastructure
| Service | Purpose |
|---|---|
| **Vercel** | Frontend hosting |
| **Render** | Backend hosting |
| **Supabase** | Database + Google OAuth |
| **GitHub** | Version control + CI/CD |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
│                    Next.js Frontend (Vercel)                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│  │Dashboard │  │ Resume   │  │Applications│  │  Job Detail  │  │
│  │Job Search│  │ Upload   │  │  Kanban   │  │  AI Co-Pilot │  │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └──────┬───────┘  │
└───────┼─────────────┼───────────────┼────────────────┼──────────┘
        │             │               │                │
        ▼             ▼               ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (Render)                       │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│  │  /jobs   │  │ /resume  │  │  /applic- │  │   /ai/*      │  │
│  │  router  │  │  router  │  │  ations   │  │  ats-score   │  │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │  cover-letter│  │
│       │             │               │         │  skills-gap  │  │
│  ┌────▼─────────────▼───────────────▼──────┐  │  interview   │  │
│  │          Job Fetcher Service             │  │  resume-impr │  │
│  │  RemoteOK │ Remotive │ Adzuna │ JSearch  │  └──────┬───────┘  │
│  └──────────────────────────────────────────┘         │          │
└──────────────────────────────────────────────────────┼──────────┘
                       │                                │
          ┌────────────▼────────────┐    ┌─────────────▼──────────┐
          │       Supabase          │    │    Google Gemini AI     │
          │  (PostgreSQL + Auth)    │    │   (gemini-2.5-flash)   │
          │                         │    │                         │
          │  • profiles             │    │  • Resume parsing       │
          │  • resumes              │    │  • ATS scoring          │
          │  • applications         │    │  • Cover letters        │
          │  • Google OAuth         │    │  • Interview prep       │
          └─────────────────────────┘    └─────────────────────────┘
```

---

## 📁 Project Structure

```
job-finder-ai/
├── 📄 render.yaml              # Render deployment config
├── 📄 supabase_setup.sql       # Database schema + RLS policies
├── 📄 .gitignore
│
├── 📁 backend/                 # FastAPI Python backend
│   ├── 📄 requirements.txt
│   ├── 📄 .env.example
│   └── 📁 app/
│       ├── 📄 main.py          # FastAPI app entry, CORS, lifespan
│       ├── 📄 config.py        # Pydantic settings (reads from .env)
│       ├── 📁 models/
│       │   └── schemas.py      # Pydantic models (Job, Profile, etc.)
│       ├── 📁 routers/
│       │   ├── jobs.py         # GET /api/jobs, /api/jobs/search
│       │   ├── ai.py           # POST /api/ai/* (all AI features)
│       │   ├── resume.py       # POST /api/resume/upload
│       │   ├── profile.py      # GET/PUT /api/profile
│       │   ├── applications.py # CRUD /api/applications
│       │   └── auth.py         # Auth utilities
│       └── 📁 services/
│           ├── job_fetcher.py  # Multi-source job aggregator + cache
│           └── ai_gemini.py    # Google Gemini AI integration
│
└── 📁 frontend/                # Next.js TypeScript frontend
    ├── 📄 package.json
    ├── 📄 next.config.ts
    ├── 📄 .env.local.example
    └── 📁 src/
        ├── 📁 app/
        │   ├── layout.tsx      # Root layout with Providers
        │   ├── providers.tsx   # ThemeProvider + Toaster
        │   ├── page.tsx        # Landing / redirect
        │   ├── login/          # Google OAuth login page
        │   ├── dashboard/      # Job search + listings
        │   ├── job/[id]/       # Job detail + AI Co-Pilot
        │   ├── resume/         # Resume upload + AI Improver
        │   ├── applications/   # Kanban board
        │   └── profile/        # User profile + skills
        ├── 📁 components/
        │   ├── navbar.tsx      # Responsive navigation
        │   ├── job-card.tsx    # Job listing card
        │   ├── search-bar.tsx  # Debounced search
        │   ├── filter-pills.tsx# Location/type filters
        │   ├── auth-guard.tsx  # Route protection
        │   └── ai/             # AI feature components
        ├── 📁 contexts/
        │   └── auth-context.tsx# Supabase auth state
        └── 📁 lib/
            ├── api.ts          # Backend API client
            └── supabase.ts     # Supabase client
```

---

## 🚀 Getting Started (Local Development)

### Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- **Supabase** account (free)
- **Google AI Studio** account (free Gemini API key)
- **Adzuna** developer account (free — 250 req/day)

### 1. Clone the Repository

```bash
git clone https://github.com/KhuzaimaHassan/job-finder-ai.git
cd job-finder-ai
```

### 2. Supabase Setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run the entire contents of `supabase_setup.sql`
3. Go to **Authentication → URL Configuration**:
   - **Site URL**: `http://localhost:3000`
   - **Redirect URLs**: Add `http://localhost:3000/**`
4. Go to **Authentication → Providers → Google** and enable it (add your Google OAuth credentials)

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Fill in your values (see Environment Variables section)

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `http://localhost:8000`  
API docs (Swagger): `http://localhost:8000/docs`

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
cp .env.local.example .env.local
# Fill in your values (see Environment Variables section)

# Start frontend
npm run dev
```

Frontend will be available at: `http://localhost:3000`

---

## 🔑 Environment Variables

### Backend (`backend/.env`)

```env
# Adzuna API — register free at developer.adzuna.com (250 req/day)
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key

# JSearch via RapidAPI — optional, free 200 req/month
JSEARCH_API_KEY=your_rapidapi_key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_role_key

# Google Gemini AI — free at aistudio.google.com
GEMINI_API_KEY=your_gemini_api_key
GEMINI_AI_MODEL=gemini-2.5-flash

# CORS — set to your frontend URL
FRONTEND_URL=http://localhost:3000
```

### Frontend (`frontend/.env.local`)

```env
# Supabase (public keys are safe to expose)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key

# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## ☁️ Deployment

### Backend → Render

1. Go to [render.com](https://render.com) → **New** → **Blueprint**
2. Connect your GitHub repository
3. Render auto-detects `render.yaml` and configures the service
4. Add all backend environment variables in the Render dashboard
5. Deploy!

The `render.yaml` is pre-configured with:
- Python 3.12, `rootDir: backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Frontend → Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import `KhuzaimaHassan/job-finder-ai` from GitHub
3. Set **Root Directory** to `frontend`
4. Add all frontend environment variables
5. Also add: `NEXT_PUBLIC_API_URL=https://your-render-service.onrender.com`
6. Deploy!

### Post-Deployment Steps

1. **Update Supabase** → Authentication → URL Configuration:
   - **Site URL**: `https://your-app.vercel.app`
   - **Redirect URLs**: `https://your-app.vercel.app/**`

2. **Update Render** → Environment Variables:
   - `FRONTEND_URL=https://your-app.vercel.app` (for CORS)

---

## 📡 API Endpoints

### Jobs
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/jobs` | Get all cached jobs (paginated) |
| `GET` | `/api/jobs/search?q=python&location=remote` | Search/filter jobs |
| `GET` | `/api/jobs/{id}` | Get single job by ID |
| `GET` | `/api/jobs/matched` | Get AI-matched jobs for user |
| `POST` | `/api/jobs/refresh` | Manually trigger job cache refresh |

### Resume
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/resume/upload` | Upload PDF, parse with AI |
| `GET` | `/api/resume` | Get user's parsed resume data |

### AI Features
| Method | Endpoint | Body | Description |
|---|---|---|---|
| `POST` | `/api/ai/ats-score` | `{resume_text, job_description}` | ATS match percentage |
| `POST` | `/api/ai/cover-letter` | `{job_title, company, job_description, resume_text}` | Generate cover letter |
| `POST` | `/api/ai/skills-gap` | `{user_skills, job_required_skills}` | Skills gap analysis |
| `POST` | `/api/ai/interview-prep` | `{job_title, job_description, user_skills}` | Interview questions |
| `POST` | `/api/ai/resume-improve` | `{resume_text, target_role}` | 5 resume improvements |

### Profile & Applications
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/profile` | Get user profile |
| `PUT` | `/api/profile` | Update profile/skills |
| `GET` | `/api/applications` | Get all user applications |
| `POST` | `/api/applications` | Create new application |
| `PATCH` | `/api/applications/{id}` | Update status/notes |
| `DELETE` | `/api/applications/{id}` | Remove application |

---

## 🗄️ Database Schema

```sql
-- Users are managed by Supabase Auth (auth.users)

-- Extended user profile
CREATE TABLE public.profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id),
  email       TEXT,
  full_name   TEXT,
  headline    TEXT,
  skills      TEXT[],       -- Array of skill strings
  location    TEXT,
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Parsed resume data
CREATE TABLE public.resumes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users(id),
  raw_text    TEXT,         -- Full extracted text
  parsed      JSONB,        -- Structured: {skills, experience, education}
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Job applications (Kanban)
CREATE TABLE public.applications (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users(id),
  job_id      TEXT NOT NULL,
  job_title   TEXT NOT NULL,
  company     TEXT NOT NULL,
  status      TEXT DEFAULT 'Saved',  -- Saved|Applied|Interview|Offer|Rejected
  notes       TEXT,
  applied_date TIMESTAMPTZ,
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

All tables have **Row Level Security (RLS)** enabled — users can only access their own data.

---

## 🌐 Job Data Sources

| Source | Type | Key Required | Jobs/Fetch |
|---|---|---|---|
| **RemoteOK** | Remote tech jobs | ❌ No key | ~20 relevant |
| **Remotive** | Remote jobs (15 queries) | ❌ No key | ~200–300 |
| **Adzuna** | International + Pakistan | ✅ Free (250/day) | ~250 |
| **JSearch** | Pakistan-specific | ✅ Free (200/month) | ~40 |

> **Note on Pakistan Jobs:** Web scraping (Indeed, Rozee.pk) is blocked from cloud servers like Render. For Pakistan-city jobs, set up your free **Adzuna** key — it supports `country=pk` and delivers consistent results from a stable API.

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Khuzaima Hassan**  
[![GitHub](https://img.shields.io/badge/GitHub-KhuzaimaHassan-black?style=flat&logo=github)](https://github.com/KhuzaimaHassan)

---

<div align="center">
  <sub>Built with ❤️ using Next.js, FastAPI, Google Gemini AI, and Supabase</sub>
</div>
