import axios from "axios";
import { supabase } from "@/lib/supabase";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import { 
  Job, JobSearchResponse, JobSearchParams, 
  UserProfileRow, ResumeInfo, ATSScoreResult, 
  SkillGapResult, InterviewQ, Application 
} from "@/types";
export * from "@/types";

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 45000, // 45 seconds to allow for Gemini PDF parsing
});

// The auth token is now set directly on api.defaults by auth-context.tsx

export async function searchJobs(
  params: JobSearchParams
): Promise<JobSearchResponse> {
  const { data } = await api.get<JobSearchResponse>("/api/jobs", { params });
  return data;
}

export async function getMatchedJobs(
  page: number = 1,
  per_page: number = 20
): Promise<JobSearchResponse> {
  const { data } = await api.get<JobSearchResponse>("/api/jobs/matched", {
    params: { page, per_page },
  });
  return data;
}

export async function getJob(id: string): Promise<Job> {
  const { data } = await api.get<Job>(`/api/jobs/${id}`);
  return data;
}

export async function getJobStats(): Promise<{
  total_jobs: number;
  by_source: Record<string, number>;
  remote_jobs: number;
}> {
  const { data } = await api.get("/api/jobs/stats");
  return data;
}

const AI_TIMEOUT_MS = 120_000;


export async function getProfile(): Promise<UserProfileRow> {
  const { data } = await api.get<UserProfileRow>("/api/profile");
  return data;
}


export async function getResumeInfo(): Promise<ResumeInfo> {
  const { data } = await api.get<ResumeInfo>("/api/resume");
  return data;
}


export async function postAiAtsScore(
  resume_text: string,
  job_description: string
): Promise<ATSScoreResult> {
  const { data } = await api.post<ATSScoreResult>(
    "/api/ai/ats-score",
    { resume_text, job_description },
    { timeout: AI_TIMEOUT_MS }
  );
  return data;
}

export async function postAiCoverLetter(body: {
  resume_text: string;
  job_title: string;
  company: string;
  job_description: string;
}): Promise<{ cover_letter: string }> {
  const { data } = await api.post<{ cover_letter: string }>(
    "/api/ai/cover-letter",
    body,
    { timeout: AI_TIMEOUT_MS }
  );
  return data;
}


export async function postAiSkillGap(
  user_skills: string,
  job_required_skills: string
): Promise<SkillGapResult> {
  const { data } = await api.post<SkillGapResult>(
    "/api/ai/skill-gap",
    { user_skills, job_required_skills },
    { timeout: AI_TIMEOUT_MS }
  );
  return data;
}


export async function postAiInterviewPrep(body: {
  job_title: string;
  job_description: string;
  user_skills: string;
}): Promise<{ questions: InterviewQ[] }> {
  const { data } = await api.post<{ questions: InterviewQ[] }>(
    "/api/ai/interview-prep",
    body,
    { timeout: AI_TIMEOUT_MS }
  );
  return data;
}

export async function postAiResumeImprove(body: {
  resume_text: string;
  target_role: string;
}): Promise<{ improvements: string[] }> {
  const { data } = await api.post<{ improvements: string[] }>(
    "/api/ai/resume-improve",
    body,
    { timeout: AI_TIMEOUT_MS }
  );
  return data;
}

// ==========================================
// Applications
// ==========================================


export async function getApplications(): Promise<Application[]> {
  const { data } = await api.get<Application[]>("/api/applications");
  return data;
}

export async function createApplication(body: {
  job_id: string;
  job_title: string;
  company: string;
  status?: string;
  notes?: string;
}): Promise<Application> {
  const { data } = await api.post<Application>("/api/applications", body);
  return data;
}

export async function updateApplication(
  appId: string,
  body: { status?: string; notes?: string }
): Promise<Application> {
  const { data } = await api.patch<Application>(`/api/applications/${appId}`, body);
  return data;
}

export async function deleteApplication(appId: string): Promise<{ success: boolean }> {
  const { data } = await api.delete<{ success: boolean }>(`/api/applications/${appId}`);
  return data;
}
