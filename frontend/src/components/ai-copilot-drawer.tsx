"use client";

import { useState, useEffect, useRef } from "react";
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
  const dialogRef = useRef<HTMLDialogElement>(null);

  // Prevent background scrolling when drawer is open
  useEffect(() => {
    if (!isOpen) return;
    const dialog = dialogRef.current;
    const previousOverflow = document.body.style.overflow;
    dialog?.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog?.close();
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen]);

  return (
    <>
      {/* Floating Action Button */}
      <button
        aria-label="Ask AI Co-Pilot"
        aria-haspopup="dialog"
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-5 py-3.5 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-semibold shadow-2xl shadow-indigo-500/25 transition-all hover:scale-105 hover:-translate-y-1"
      >
        <Sparkles className="w-5 h-5 animate-pulse" />
        <span className="hidden sm:inline">Ask AI Co-Pilot</span>
      </button>

      {/* Native modal: closed dialogs are hidden and cannot intercept input.
          showModal also traps focus and restores it to the launcher on close. */}
      <dialog
        ref={dialogRef}
        aria-labelledby="ai-copilot-title"
        onClose={(event) => {
          if (!event.currentTarget.open) setIsOpen(false);
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget) setIsOpen(false);
        }}
        className="m-auto w-[calc(100%-1rem)] sm:w-[calc(100%-3rem)] max-w-4xl max-h-[calc(100dvh-1rem)] border-0 bg-transparent p-0 text-white backdrop:bg-black/60 backdrop:backdrop-blur-sm"
      >
        <div 
          className="w-full min-w-0 h-[calc(100dvh-1rem)] sm:h-[85dvh] bg-[#0a0a0f] border border-zinc-800/80 shadow-2xl rounded-2xl flex flex-col"
        >
        {/* Header */}
        <div className="flex items-center justify-between gap-3 p-4 sm:p-6 border-b border-zinc-800 bg-[#0a0a0f] shrink-0 rounded-t-2xl">
          <h2 id="ai-copilot-title" className="text-xl font-bold flex items-center gap-2 text-white">
            <span className="text-indigo-400"><Sparkles className="w-5 h-5" /></span> 
            AI Co-Pilot
          </h2>
          <button 
            aria-label="Close AI Co-Pilot"
            onClick={() => setIsOpen(false)}
            className="p-2 rounded-xl bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-3 sm:p-6 space-y-4 sm:space-y-6 break-words">
          {!resumeText ? (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-4 text-zinc-400">
              <div className="p-4 bg-zinc-900 rounded-full border border-zinc-800">
                <Sparkles className="w-8 h-8 text-indigo-400 opacity-50" />
              </div>
              <p className="text-lg font-medium text-white">AI Co-Pilot Needs Your Resume</p>
              <p className="max-w-md mx-auto text-sm">
                To generate a personalized Cover Letter, calculate an ATS Score, and analyze your skills gap, the AI needs to read your resume.
              </p>
              <a 
                href="/resume" 
                className="mt-4 inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium transition-colors"
              >
                Upload Resume
              </a>
            </div>
          ) : (
            <>
              <p className="text-sm text-zinc-400 mb-2">
                Your personal AI assistant is ready. Analyze your resume, generate a cover letter, and prep for interviews.
              </p>
              <ATSScore jobDescription={job.description} resumeText={resumeText} />
              <CoverLetter jobTitle={job.title} company={job.company} jobDescription={job.description} resumeText={resumeText} />
              <SkillsGapAnalysis userSkills={userSkills} jobRequiredSkills={requiredSkills} jobDescription={job.description} resumeText={resumeText} />
              <InterviewPrep jobTitle={job.title} jobDescription={job.description} userSkills={userSkills} resumeText={resumeText} />
            </>
          )}
        </div>
        </div>
      </dialog>
    </>
  );
}
