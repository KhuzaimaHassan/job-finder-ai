export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  salary: string | null;
  description: string;
  url: string;
  source: "adzuna" | "remoteok" | "remotive" | "indeed" | "google" | "jsearch" | "jobicy" | "himalayas" | "linkedin" | "supabase" | string;
  posted_date: string | null;
  tags: string[];
  job_type: string | null;
  match_score?: number;
}

export interface JobSearchResponse {
  jobs: Job[];
  total: number;
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface JobSearchParams {
  q?: string;
  location?: string;
  job_type?: string;
  source?: string;
  page?: number;
  per_page?: number;
}

export interface UserProfileRow {
  user_id?: string;
  name?: string;
  email?: string;
  skills?: string[];
  experience_years?: number;
  target_roles?: string[];
  location?: string;
}

export interface ResumeInfo {
  parsed: boolean;
  raw_text?: string;
  skills?: string[];
  education?: unknown[];
  experience?: unknown[];
  projects?: unknown[];
  parsed_at?: string;
}

export interface ATSScoreResult {
  score: number;
  matching_keywords: string[];
  missing_keywords: string[];
  verdict: string;
}

export interface SkillGapResult {
  missing_skills: string[];
  courses: {
    name: string;
    platform: string;
    url: string;
    free: boolean;
  }[];
}

export interface InterviewQ {
  question: string;
  answer_structure: string;
}

export interface Application {
  id: string;
  user_id: string;
  job_id: string;
  job_title: string;
  company: string;
  status: 'Saved' | 'Applied' | 'Interview' | 'Offer' | 'Rejected';
  notes: string;
  applied_date: string;
  updated_at: string;
}
