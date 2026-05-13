"use client";

import { useState } from "react";
import { postAiResumeImprove } from "@/lib/api";
import { Loader2, Sparkles, CheckCircle2, Circle } from "lucide-react";
import { toast } from "sonner";

interface ResumeImproverProps {
  resumeText: string;
}

export function ResumeImprover({ resumeText }: ResumeImproverProps) {
  const [targetRole, setTargetRole] = useState("");
  const [loading, setLoading] = useState(false);
  const [improvements, setImprovements] = useState<string[] | null>(null);
  const [completed, setCompleted] = useState<Set<number>>(new Set());

  const handleImprove = async () => {
    if (!resumeText) {
      toast.error("Please upload a resume first");
      return;
    }
    setLoading(true);
    try {
      const data = await postAiResumeImprove({
        resume_text: resumeText,
        target_role: targetRole || "General",
      });
      setImprovements(data.improvements);
      setCompleted(new Set());
      toast.success("AI analysis complete!");
    } catch (err: any) {
      let msg = "Failed to analyze resume";
      if (err?.response?.data?.detail) {
        msg = typeof err.response.data.detail === "string" 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail);
      }
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const toggleCheck = (index: number) => {
    setCompleted((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 md:p-8 mt-8">
      <div className="flex items-center gap-3 mb-4">
        <Sparkles className="w-6 h-6 text-indigo-400" />
        <h2 className="text-xl font-bold text-white">AI Resume Improver</h2>
      </div>
      
      {!improvements && (
        <div className="space-y-4">
          <p className="text-zinc-400 text-sm">
            Get 5 highly actionable suggestions tailored to your target role to make your resume stand out.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              placeholder="Target Role (e.g., Senior React Developer)"
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value)}
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
            />
            <button
              onClick={handleImprove}
              disabled={loading}
              className="flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Analyzing...
                </>
              ) : (
                "Improve My Resume"
              )}
            </button>
          </div>
        </div>
      )}

      {improvements && (
        <div className="space-y-4">
          <p className="text-zinc-300 text-sm mb-6">
            Here are 5 specific improvements for a <span className="font-semibold text-indigo-400">{targetRole || "General"}</span> role:
          </p>
          <div className="space-y-3">
            {improvements.map((imp, idx) => {
              const isDone = completed.has(idx);
              return (
                <div 
                  key={idx}
                  onClick={() => toggleCheck(idx)}
                  className={`flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-all ${
                    isDone 
                      ? 'bg-emerald-500/5 border-emerald-500/20 opacity-60' 
                      : 'bg-zinc-950 border-zinc-800 hover:border-indigo-500/30'
                  }`}
                >
                  <div className="mt-0.5 shrink-0">
                    {isDone ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    ) : (
                      <Circle className="w-5 h-5 text-zinc-600" />
                    )}
                  </div>
                  <p className={`text-sm leading-relaxed ${isDone ? 'text-zinc-500 line-through' : 'text-zinc-200'}`}>
                    {imp}
                  </p>
                </div>
              );
            })}
          </div>
          <div className="pt-4 flex justify-end">
             <button
              onClick={() => setImprovements(null)}
              className="text-sm text-zinc-400 hover:text-white transition-colors underline"
            >
              Analyze a different role
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
