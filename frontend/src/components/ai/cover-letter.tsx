"use client";

import { useState } from "react";
import { postAiCoverLetter } from "@/lib/api";
import { Loader2, Copy, Check } from "lucide-react";

interface CoverLetterProps {
  jobTitle: string;
  company: string;
  jobDescription: string;
  resumeText: string | null;
}

export function CoverLetter({ jobTitle, company, jobDescription, resumeText }: CoverLetterProps) {
  const [loading, setLoading] = useState(false);
  const [letter, setLetter] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async () => {
    if (!resumeText) {
      setError("Please upload your resume in the Resume page first.");
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const data = await postAiCoverLetter({ resume_text: resumeText, job_title: jobTitle, company, job_description: jobDescription });
      setLetter(data.cover_letter);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to generate cover letter");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (letter) {
      navigator.clipboard.writeText(letter);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">AI Cover Letter</h3>
        {!letter && !loading && (
          <button
            onClick={handleGenerate}
            className="px-4 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-sm font-medium transition-colors"
          >
            Generate
          </button>
        )}
      </div>
      
      {!letter && !loading && (
        <p className="text-sm text-zinc-400">
          Generate a personalized, 3-paragraph cover letter tailored to this exact role and your resume.
        </p>
      )}

      {error && <p className="text-red-400 text-xs mt-3">{error}</p>}

      {loading && (
        <div className="flex flex-col items-center justify-center py-8">
          <Loader2 className="h-6 w-6 text-blue-500 animate-spin mb-3" />
          <p className="text-sm text-zinc-400">Drafting your cover letter...</p>
        </div>
      )}

      {letter && (
        <div className="mt-4">
          <div className="relative group">
            <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-5 text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
              {letter}
            </div>
            <button
              onClick={copyToClipboard}
              className="absolute top-3 right-3 p-2 bg-zinc-800 hover:bg-zinc-700 rounded-md border border-zinc-700 transition-colors"
              title="Copy to clipboard"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-zinc-300" />}
            </button>
          </div>
          <button
            onClick={handleGenerate}
            className="mt-4 text-xs text-zinc-500 hover:text-zinc-300 underline"
          >
            Regenerate
          </button>
        </div>
      )}
    </div>
  );
}
