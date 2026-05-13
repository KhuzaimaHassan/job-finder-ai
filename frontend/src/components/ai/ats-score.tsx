"use client";

import { useState } from "react";
import { postAiAtsScore } from "@/lib/api";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";

interface ATSScoreProps {
  jobDescription: string;
  resumeText: string | null;
}

export function ATSScore({ jobDescription, resumeText }: ATSScoreProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCalculate = async () => {
    if (!resumeText) {
      setError("Please upload your resume in the Resume page first.");
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const data = await postAiAtsScore(resumeText, jobDescription);
      setResult(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to calculate ATS score");
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return "text-emerald-400";
    if (score >= 40) return "text-amber-400";
    return "text-red-400";
  };

  const getScoreBg = (score: number) => {
    if (score >= 70) return "bg-emerald-500/10 border-emerald-500/20";
    if (score >= 40) return "bg-amber-500/10 border-amber-500/20";
    return "bg-red-500/10 border-red-500/20";
  };

  if (!result && !loading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-2">ATS Compatibility Score</h3>
        <p className="text-sm text-zinc-400 mb-4">
          See how well your resume matches this job description before applying.
        </p>
        <button
          onClick={handleCalculate}
          className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-sm font-medium transition-colors"
        >
          Calculate ATS Score
        </button>
        {error && <p className="text-red-400 text-xs mt-3">{error}</p>}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 flex flex-col items-center justify-center min-h-[200px]">
        <Loader2 className="h-8 w-8 text-indigo-500 animate-spin mb-3" />
        <p className="text-sm text-zinc-400">Analyzing resume vs job description...</p>
      </div>
    );
  }

  return (
    <div className={`border rounded-xl p-6 ${getScoreBg(result.score)}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">ATS Score</h3>
        <div className={`text-2xl font-bold ${getScoreColor(result.score)}`}>
          {result.score}%
        </div>
      </div>
      
      <p className="text-sm text-zinc-300 mb-6">{result.verdict}</p>

      <div className="space-y-4">
        {result.matching_keywords?.length > 0 && (
          <div>
            <p className="text-xs font-medium text-emerald-400 mb-2 uppercase tracking-wider">Matching Keywords</p>
            <div className="flex flex-wrap gap-1.5">
              {result.matching_keywords.map((kw: string) => (
                <span key={kw} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                  <CheckCircle2 className="w-3 h-3" /> {kw}
                </span>
              ))}
            </div>
          </div>
        )}

        {result.missing_keywords?.length > 0 && (
          <div>
            <p className="text-xs font-medium text-red-400 mb-2 uppercase tracking-wider">Missing Keywords</p>
            <div className="flex flex-wrap gap-1.5">
              {result.missing_keywords.map((kw: string) => (
                <span key={kw} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-red-500/10 text-red-300 border border-red-500/20">
                  <XCircle className="w-3 h-3" /> {kw}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
