"use client";

import { AuthGuard } from "@/components/auth-guard";
import { Navbar } from "@/components/navbar";
import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { UploadCloud, FileText, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { ResumeImprover } from "@/components/ai/resume-improver";

export default function ResumePage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parsedData, setParsedData] = useState<any | null>(null);
  const [existingResumeText, setExistingResumeText] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const fetchExisting = async () => {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await axios.get(`${API_URL}/api/resume`);
        if (res.data && res.data.parsed) {
          setExistingResumeText(res.data.raw_text);
        }
      } catch (err) {
        // No existing resume
      } finally {
        setLoading(false);
      }
    };
    fetchExisting();
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (selected.type !== "application/pdf") {
        setError("Only PDF files are supported");
        setFile(null);
        return;
      }
      if (selected.size > 10 * 1024 * 1024) {
        setError("File size must be under 10MB");
        setFile(null);
        return;
      }
      setFile(selected);
      setError(null);
      setSuccess(false);
      setParsedData(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    
    const formData = new FormData();
    formData.append("file", file);

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const { data } = await axios.post(`${API_URL}/api/resume/upload`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      
      setSuccess(true);
      setParsedData(data);
      
      // Auto-sync profile with resume data
      try {
        await axios.post(`${API_URL}/api/profile/sync-from-resume`);
      } catch (syncErr) {
        console.error("Profile sync failed", syncErr);
      }
      
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || "Failed to upload and parse resume");
    } finally {
      setUploading(false);
    }
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-[#0a0a0f] text-white">
        <Navbar />
        
        <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Resume Upload</h1>
            <p className="text-zinc-400">
              Upload your resume so our AI can match you with the best jobs.
            </p>
          </div>

          <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-8 backdrop-blur-sm mb-8">
            <div 
              className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center transition-colors
                ${file ? "border-indigo-500/50 bg-indigo-500/5" : "border-zinc-700 bg-zinc-800/30 hover:border-zinc-500"}
                ${error ? "border-red-500/50 bg-red-500/5" : ""}
              `}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                  const dataTransferFile = e.dataTransfer.files[0];
                  if (dataTransferFile.type === "application/pdf") {
                    setFile(dataTransferFile);
                    setError(null);
                  } else {
                    setError("Only PDF files are supported");
                  }
                }
              }}
            >
              {file ? (
                <div className="flex flex-col items-center">
                  <FileText className="h-12 w-12 text-indigo-400 mb-4" />
                  <p className="text-lg font-medium text-zinc-200">{file.name}</p>
                  <p className="text-sm text-zinc-500 mb-6">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  <div className="flex gap-4">
                    <button 
                      onClick={() => setFile(null)}
                      className="px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-white transition-colors"
                      disabled={uploading}
                    >
                      Cancel
                    </button>
                    <button 
                      onClick={handleUpload}
                      disabled={uploading}
                      className="px-6 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
                    >
                      {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                      {uploading ? "Analyzing with AI..." : "Upload & Parse"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center text-center">
                  <div className="h-16 w-16 rounded-full bg-zinc-800 flex items-center justify-center mb-4">
                    <UploadCloud className="h-8 w-8 text-zinc-400" />
                  </div>
                  <p className="text-lg font-medium text-zinc-200 mb-1">Drag and drop your resume</p>
                  <p className="text-sm text-zinc-500 mb-6">PDF files only, up to 10MB</p>
                  <input 
                    type="file" 
                    accept=".pdf" 
                    className="hidden" 
                    ref={fileInputRef}
                    onChange={handleFileChange}
                  />
                  <button 
                    onClick={() => fileInputRef.current?.click()}
                    className="px-6 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white text-sm font-medium transition-colors border border-zinc-700"
                  >
                    Select File
                  </button>
                </div>
              )}
            </div>

            {error && (
              <div className="mt-4 p-4 rounded-lg bg-red-500/10 border border-red-500/20 flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
                <p className="text-sm text-red-300">{error}</p>
              </div>
            )}

            {success && (
              <div className="mt-4 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                <p className="text-sm text-emerald-300">Resume successfully parsed and skills extracted. Your profile has been updated!</p>
              </div>
            )}
          </div>

          {parsedData && (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <h2 className="text-xl font-semibold border-b border-zinc-800 pb-2">Extracted Data</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5">
                  <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wider">Top Skills</h3>
                  <div className="flex flex-wrap gap-2">
                    {parsedData.skills?.map((skill: string, i: number) => (
                      <span key={i} className="px-2.5 py-1 rounded-md bg-indigo-500/10 text-indigo-300 text-xs border border-indigo-500/20">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5">
                  <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wider">Experience</h3>
                  <div className="space-y-4">
                    {parsedData.experience?.map((exp: any, i: number) => (
                      <div key={i} className="border-l-2 border-zinc-800 pl-3">
                        <p className="font-medium text-sm text-zinc-200">{exp.title}</p>
                        <p className="text-xs text-zinc-500">{exp.company} • {exp.duration}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* AI Resume Improver */}
          {(parsedData?.raw_text || existingResumeText) && (
            <ResumeImprover resumeText={parsedData?.raw_text || existingResumeText} />
          )}

        </main>
      </div>
    </AuthGuard>
  );
}
