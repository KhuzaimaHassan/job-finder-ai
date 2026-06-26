"use client";

import { useState, useEffect } from "react";
import { X, Sparkles } from "lucide-react";
import { ATSScore } from "@/components/ai/ats-score";
import { CoverLetter } from "@/components/ai/cover-letter";
import { SkillsGapAnalysis } from "@/components/ai/skills-gap";
import { InterviewPrep } from "@/components/ai/interview-prep";

interface AICopilotDrawerProps {
  job: {
    title: string;
    company: string;
    description: string;
  };
  userSkills: string[];
  resumeText: string | null;
  requiredSkills: string[];
}

export function AICopilotDrawer({ job, userSkills, resumeText, requiredSkills }: AICopilotDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Prevent background scrolling when drawer is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  return (
    <>
      {/* Floating Action Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-5 py-3.5 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-semibold shadow-2xl shadow-indigo-500/25 transition-all hover:scale-105 hover:-translate-y-1"
      >
        <Sparkles className="w-5 h-5 animate-pulse" />
        <span className="hidden sm:inline">Ask AI Co-Pilot</span>
      </button>

      {/* Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm transition-opacity"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Drawer */}
      <div 
        className={`fixed top-0 right-0 z-50 h-[100dvh] w-full sm:w-[480px] bg-[#0a0a0f] border-l border-zinc-800/80 shadow-2xl transform transition-transform duration-300 ease-in-out flex flex-col ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-800 bg-[#0a0a0f] shrink-0">
          <h2 className="text-xl font-bold flex items-center gap-2 text-white">
            <span className="text-indigo-400"><Sparkles className="w-5 h-5" /></span> 
            AI Co-Pilot
          </h2>
          <button 
            onClick={() => setIsOpen(false)}
            className="p-2 rounded-xl bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
          <p className="text-sm text-zinc-400 mb-2">
            Your personal AI assistant is ready. Analyze your resume, generate a cover letter, and prep for interviews.
          </p>
          <ATSScore jobDescription={job.description} resumeText={resumeText} />
          <CoverLetter jobTitle={job.title} company={job.company} jobDescription={job.description} resumeText={resumeText} />
          <SkillsGapAnalysis userSkills={userSkills} jobRequiredSkills={requiredSkills} />
          <InterviewPrep jobTitle={job.title} jobDescription={job.description} userSkills={userSkills} />
        </div>
      </div>
    </>
  );
}
