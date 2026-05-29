"use client";

import Link from "next/link";
import { type Job } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

const SOURCE_COLORS: Record<string, string> = {
  adzuna: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  remoteok: "bg-blue-500/15 text-blue-400 border-blue-500/20",
  remotive: "bg-purple-500/15 text-purple-400 border-purple-500/20",
  indeed: "bg-indigo-500/15 text-indigo-400 border-indigo-500/20",
  google: "bg-teal-500/15 text-teal-400 border-teal-500/20",
  jsearch: "bg-orange-500/15 text-orange-400 border-orange-500/20",
  himalayas: "bg-cyan-500/15 text-cyan-400 border-cyan-500/20",
  jobicy: "bg-rose-500/15 text-rose-400 border-rose-500/20",
};

const SOURCE_LABELS: Record<string, string> = {
  adzuna: "Adzuna",
  remoteok: "RemoteOK",
  remotive: "Remotive",
  indeed: "Indeed",
  google: "Google Jobs",
  jsearch: "JSearch",
  himalayas: "Himalayas",
  jobicy: "Jobicy",
};

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  try {
    // Handle relative strings from LinkedIn/Indeed (e.g. "3 days ago", "2 weeks ago")
    const lower = dateStr.toLowerCase().trim();
    if (lower.includes("just") || lower.includes("hour")) return "Today";
    if (lower === "today") return "Today";
    if (lower === "yesterday") return "1 day ago";
    const relMatch = lower.match(/(\d+)\s*(day|week|month|year)/);
    if (relMatch) {
      const n = parseInt(relMatch[1]);
      const unit = relMatch[2];
      if (unit === "day") return n === 1 ? "1 day ago" : `${n} days ago`;
      if (unit === "week") return `${n}w ago`;
      if (unit === "month") return `${n}mo ago`;
      if (unit === "year") return `${n}y ago`;
    }

    // Parse actual date strings (ISO, YYYY-MM-DD, etc.)
    const date = new Date(dateStr);
    // Guard against Invalid Date (new Date("garbage") doesn't throw — it returns NaN)
    if (isNaN(date.getTime())) return "";

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    if (diffMs < 0) return "Today"; // future date edge case
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "1 day ago";
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
    return `${Math.floor(diffDays / 365)}y ago`;
  } catch {
    return "";
  }
}

export function JobCard({ job }: { job: Job }) {
  return (
    <div className="group relative rounded-xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm p-5 hover:border-purple-500/30 hover:bg-white/[0.04] transition-all duration-300 flex flex-col h-full">
      {/* Hover glow */}
      <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-purple-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />

      <div className="relative z-10 flex flex-col flex-1">
        {/* Header — source + time */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={`text-[11px] font-medium px-2 py-0.5 ${SOURCE_COLORS[job.source] || "bg-gray-500/15 text-gray-400"}`}>
              {SOURCE_LABELS[job.source] || job.source}
            </Badge>
            {job.match_score !== undefined && (
              <Badge variant="outline" className="text-[11px] font-medium px-2 py-0.5 bg-pink-500/15 text-pink-400 border-pink-500/30">
                <span className="mr-1">✨</span> {job.match_score}% Match
              </Badge>
            )}
          </div>
          {job.posted_date && (
            <span className="text-[11px] text-gray-500">{timeAgo(job.posted_date)}</span>
          )}
        </div>

        {/* Title */}
        <h3 className="text-[15px] font-semibold text-white leading-snug mb-1.5 line-clamp-2 group-hover:text-purple-300 transition-colors">
          {job.title}
        </h3>

        {/* Company */}
        <p className="text-sm text-gray-400 mb-1">{job.company}</p>

        {/* Location */}
        <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-3">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
          <span className="truncate">{job.location || "Remote"}</span>
        </div>

        {/* Salary */}
        {job.salary && (
          <div className="flex items-center gap-1.5 text-xs text-emerald-400/90 mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" /></svg>
            <span>{job.salary}</span>
          </div>
        )}

        {/* Tags */}
        {job.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {[...new Set(job.tags)].slice(0, 5).map((tag, i) => (
              <span
                key={`${tag}-${i}`}
                className="text-[11px] px-2 py-0.5 rounded-md bg-white/[0.05] text-gray-400 border border-white/[0.06]"
              >
                {tag}
              </span>
            ))}
            {job.tags.length > 5 && (
              <span className="text-[11px] px-2 py-0.5 text-gray-500">
                +{job.tags.length - 5}
              </span>
            )}
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Description preview */}
        <p className="text-xs text-gray-500 line-clamp-2 mb-4 leading-relaxed">
          {job.description?.replace(/<[^>]+>/g, "").slice(0, 150)}
        </p>

        <div className="flex gap-2">
          <Link
            href={`/job/${encodeURIComponent(job.id)}`}
            className="flex-1 text-center py-2.5 rounded-lg text-sm font-medium border border-white/15 bg-white/[0.04] hover:bg-white/[0.08] text-white transition-colors"
          >
            Details &amp; AI
          </Link>
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 text-center py-2.5 rounded-lg text-sm font-medium bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white transition-all duration-200 shadow-lg shadow-purple-500/10 hover:shadow-purple-500/20"
          >
            Apply →
          </a>
        </div>
      </div>
    </div>
  );
}
