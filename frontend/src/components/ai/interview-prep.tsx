"use client";

import { useState } from "react";
import { postAiInterviewPrep } from "@/lib/api";
import { Loader2, MessageSquare, ChevronDown, ChevronUp } from "lucide-react";

interface InterviewPrepProps {
  jobTitle: string;
  jobDescription: string;
  userSkills: string[];
}

export function InterviewPrep({ jobTitle, jobDescription, userSkills }: InterviewPrepProps) {
  const [loading, setLoading] = useState(false);
  const [questions, setQuestions] = useState<any[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await postAiInterviewPrep({
        job_title: jobTitle,
        job_description: jobDescription,
        user_skills: userSkills.join(", ")
      });
      setQuestions(data.questions);
    } catch (err: any) {
      let errorMessage = "Failed to generate interview prep";
      if (err?.response?.data?.detail) {
        errorMessage = typeof err.response.data.detail === "string" 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail);
      }
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const toggleAccordion = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-purple-400" /> Interview Prep
        </h3>
        {!questions && !loading && (
          <button
            onClick={handleGenerate}
            className="px-4 py-1.5 rounded-md bg-purple-600 hover:bg-purple-700 text-sm font-medium transition-colors"
          >
            Generate Questions
          </button>
        )}
      </div>

      {!questions && !loading && (
        <p className="text-sm text-zinc-400">
          Get 5 tailored interview questions and ideal answer structures based on this job and your skills.
        </p>
      )}

      {error && <p className="text-red-400 text-xs mt-3">{error}</p>}

      {loading && (
        <div className="flex flex-col items-center justify-center py-8">
          <Loader2 className="h-6 w-6 text-purple-500 animate-spin mb-3" />
          <p className="text-sm text-zinc-400">Crafting personalized interview questions...</p>
        </div>
      )}

      {questions && (
        <div className="space-y-3 mt-4">
          {questions.map((q: any, idx: number) => (
            <div key={idx} className="border border-zinc-800 rounded-lg bg-zinc-950 overflow-hidden">
              <button
                onClick={() => toggleAccordion(idx)}
                className="w-full flex items-center justify-between p-4 text-left hover:bg-zinc-900 transition-colors"
              >
                <span className="text-sm font-medium text-zinc-200 pr-4">
                  <span className="text-purple-400 mr-2">Q{idx + 1}.</span>
                  {q.question}
                </span>
                {expandedIndex === idx ? (
                  <ChevronUp className="w-4 h-4 text-zinc-500 shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-zinc-500 shrink-0" />
                )}
              </button>
              
              {expandedIndex === idx && (
                <div className="px-4 pb-4 pt-1 border-t border-zinc-800/50 bg-zinc-900/30">
                  <p className="text-xs font-semibold text-emerald-400 mb-2 uppercase tracking-wider">How to answer:</p>
                  <p className="text-sm text-zinc-400 whitespace-pre-wrap leading-relaxed">
                    {q.answer_structure}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
