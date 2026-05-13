"use client";

import { useState, useEffect } from "react";
import { getJobStats } from "@/lib/api";

export function StatsBar() {
  const [stats, setStats] = useState<{
    total_jobs: number;
    remote_jobs: number;
    by_source: Record<string, number>;
  } | null>(null);

  useEffect(() => {
    getJobStats()
      .then(setStats)
      .catch(() => {});
  }, []);

  if (!stats) return null;

  return (
    <div className="hidden sm:flex items-center gap-4 text-xs text-gray-500">
      <span className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        {stats.total_jobs} jobs
      </span>
      <span>{stats.remote_jobs} remote</span>
    </div>
  );
}
