"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getJob, type Job } from "@/lib/api";
import { AuthGuard } from "@/components/auth-guard";
import { Navbar } from "@/components/navbar";
import { Loader2, ArrowLeft, ExternalLink, MapPin, Building, Briefcase, Calendar } from "lucide-react";
import axios from "axios";

// AI Components
import { ATSScore } from "@/components/ai/ats-score";
import { CoverLetter } from "@/components/ai/cover-letter";
import { SkillsGapAnalysis } from "@/components/ai/skills-gap";
import { InterviewPrep } from "@/components/ai/interview-prep";

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // User profile & resume data needed for AI features
  const [userProfile, setUserProfile] = useState<any>(null);
  const [resumeText, setResumeText] = useState<string | null>(null);

  useEffect(() => {
    const fetchJobAndUser = async () => {
      try {
        const jobId = Array.isArray(params.id) ? params.id[0] : params.id;
        if (!jobId) return;

        // Fetch Job
        const jobData = await getJob(jobId);
        setJob(jobData);

        // Fetch User Profile and Resume
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        
        try {
          const profileRes = await axios.get(`${API_URL}/api/profile`);
          setUserProfile(profileRes.data);
        } catch (e) {
          console.error("Could not fetch profile", e);
        }

        try {
          const resumeRes = await axios.get(`${API_URL}/api/resume`);
          if (resumeRes.data.parsed) {
            setResumeText(resumeRes.data.raw_text);
          }
        } catch (e) {
          console.error("Could not fetch resume", e);
        }

      } catch (err: any) {
        console.error("Error fetching job details:", err);
        setError("Could not load job details. It might have been removed.");
      } finally {
        setLoading(false);
      }
    };

    fetchJobAndUser();
  }, [params.id]);

  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col">
          <Navbar />
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
          </div>
        </div>
      </AuthGuard>
    );
  }

  if (error || !job) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col">
          <Navbar />
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
            <p className="text-red-400 mb-4">{error || "Job not found"}</p>
            <button onClick={() => router.push("/dashboard")} className="text-indigo-400 hover:text-indigo-300 underline">
              Back to Dashboard
            </button>
          </div>
        </div>
      </AuthGuard>
    );
  }

  const userSkills = userProfile?.skills || [];
  const requiredSkills = job.tags || [];

  return (
    <AuthGuard>
      <div className="min-h-screen bg-[#0a0a0f] text-white">
        <Navbar />
        
        <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
          <button 
            onClick={() => router.back()}
            className="flex items-center gap-2 text-sm text-zinc-400 hover:text-white mb-6 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back to jobs
          </button>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* Left Column: Job Details */}
            <div className="lg:col-span-2 space-y-6">
              
              {/* Job Header */}
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 md:p-8">
                <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
                  <div>
                    <h1 className="text-2xl md:text-3xl font-bold text-white mb-2">{job.title}</h1>
                    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-zinc-400">
                      <span className="flex items-center gap-1.5"><Building className="w-4 h-4" /> {job.company}</span>
                      <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4" /> {job.location || "Remote"}</span>
                      {job.job_type && <span className="flex items-center gap-1.5"><Briefcase className="w-4 h-4" /> {job.job_type}</span>}
                      {job.posted_date && <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4" /> {new Date(job.posted_date).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full sm:w-auto">
                    <button
                      onClick={async () => {
                        try {
                          await import("@/lib/api").then(m => m.createApplication({
                            job_id: job.id,
                            job_title: job.title,
                            company: job.company
                          }));
                          import("sonner").then(m => m.toast.success("Added to Tracker!"));
                        } catch(e) {
                          import("sonner").then(m => m.toast.error("Failed to add to tracker"));
                        }
                      }}
                      className="flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white font-medium transition-colors whitespace-nowrap"
                    >
                      Add to Tracker
                    </button>
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium transition-colors whitespace-nowrap"
                    >
                      Apply Now <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>

                {job.tags && job.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-6">
                    {job.tags.map(tag => (
                      <span key={tag} className="px-2.5 py-1 rounded bg-zinc-800 text-zinc-300 text-xs font-medium">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                
                {job.salary && (
                  <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-medium">
                    💰 {job.salary}
                  </div>
                )}

                <div className="prose prose-invert max-w-none prose-p:text-zinc-300 prose-a:text-indigo-400">
                  <h3 className="text-lg font-semibold text-white mb-3">Job Description</h3>
                  <div 
                    className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap"
                    dangerouslySetInnerHTML={{ __html: job.description }}
                  />
                </div>
              </div>

            </div>

            {/* Right Column: AI Features */}
            <div className="space-y-6">
              <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
                <span className="text-indigo-400">✨</span> AI Co-Pilot
              </h2>

              {/* ATS Score */}
              <ATSScore 
                jobDescription={job.description} 
                resumeText={resumeText} 
              />

              {/* Cover Letter Generator */}
              <CoverLetter 
                jobTitle={job.title}
                company={job.company}
                jobDescription={job.description}
                resumeText={resumeText}
              />

              {/* Skills Gap Analysis */}
              <SkillsGapAnalysis 
                userSkills={userSkills}
                jobRequiredSkills={requiredSkills}
              />

              {/* Interview Prep */}
              <InterviewPrep 
                jobTitle={job.title}
                jobDescription={job.description}
                userSkills={userSkills}
              />
            </div>
          </div>
        </main>
      </div>
    </AuthGuard>
  );
}
