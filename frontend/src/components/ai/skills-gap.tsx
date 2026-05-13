"use client";

import { useState } from "react";
import { postAiSkillGap } from "@/lib/api";
import { Loader2, BookOpen, ExternalLink, AlertTriangle } from "lucide-react";

interface SkillsGapProps {
  userSkills: string[];
  jobRequiredSkills: string[];
}

export function SkillsGapAnalysis({ userSkills, jobRequiredSkills }: SkillsGapProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await postAiSkillGap(
        userSkills.join(", "),
        jobRequiredSkills.join(", ")
      );
      setResult(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to analyze skills gap");
    } finally {
      setLoading(false);
    }
  };

  if (!result && !loading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-2">Skills Gap Analysis</h3>
        <p className="text-sm text-zinc-400 mb-4">
          Discover missing skills and get free course recommendations to level up.
        </p>
        <button
          onClick={handleAnalyze}
          className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-sm font-medium transition-colors"
        >
          Analyze Skills Gap
        </button>
        {error && <p className="text-red-400 text-xs mt-3">{error}</p>}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 flex flex-col items-center justify-center min-h-[200px]">
        <Loader2 className="h-8 w-8 text-indigo-500 animate-spin mb-3" />
        <p className="text-sm text-zinc-400">Finding courses and missing skills...</p>
      </div>
    );
  }

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <h3 className="text-lg font-semibold mb-4">Skills Gap Analysis</h3>
      
      {result.missing_skills?.length > 0 ? (
        <div className="mb-6">
          <p className="text-sm font-medium text-amber-400 flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4" /> Areas for Improvement
          </p>
          <div className="flex flex-wrap gap-2">
            {result.missing_skills.map((skill: string) => (
              <span key={skill} className="px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-300 text-xs border border-amber-500/20">
                {skill}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <div className="mb-6 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
          You have all the key skills required for this role!
        </div>
      )}

      <div>
        <p className="text-sm font-medium text-indigo-400 flex items-center gap-2 mb-3">
          <BookOpen className="w-4 h-4" /> Recommended Free Courses
        </p>
        <div className="space-y-3">
          {result.courses?.map((course: any, idx: number) => (
            <a
              key={idx}
              href={course.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block p-3 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-800/50 hover:border-indigo-500/30 transition-all group"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h4 className="text-sm font-medium text-zinc-200 group-hover:text-indigo-300 transition-colors line-clamp-1">
                    {course.name}
                  </h4>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-zinc-500">{course.platform}</span>
                    {course.free && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Free
                      </span>
                    )}
                  </div>
                </div>
                <ExternalLink className="w-4 h-4 text-zinc-600 group-hover:text-indigo-400 transition-colors shrink-0" />
              </div>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
