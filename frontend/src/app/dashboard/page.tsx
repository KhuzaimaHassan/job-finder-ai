"use client";

import { useState, useEffect } from "react";
import { searchJobs, getMatchedJobs, type Job, type JobSearchParams, type JobSearchResponse } from "@/lib/api";
import { JobCard } from "@/components/job-card";
import { SearchBar } from "@/components/search-bar";
import { FilterPills } from "@/components/filter-pills";
import { JobCardSkeleton } from "@/components/job-card-skeleton";

import { Navbar } from "@/components/navbar";
import { AuthGuard } from "@/components/auth-guard";
import { Sparkles, Globe } from "lucide-react";

export default function DashboardPage() {
  const [matchMode, setMatchMode] = useState<"all" | "matched">("all");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filters, setFilters] = useState<{
    job_type?: string;
    location?: string;
    source?: string;
  }>({});
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let active = true;

    const fetchJobs = async () => {
      setLoading(true);
      setError(null);

      const params: JobSearchParams = {
        q: searchQuery || undefined,
        location: filters.location || undefined,
        job_type: filters.job_type || undefined,
        source: filters.source || undefined,
        page: page,
        per_page: 20,
      };

      try {
        let data: JobSearchResponse;
        if (matchMode === "matched") {
          data = await getMatchedJobs(page, 20);
        } else {
          data = await searchJobs(params);
        }
        if (!active) return;
        setJobs(data.jobs);
        setTotal(data.total);
        setHasMore(data.has_more);
      } catch (err: unknown) {
        if (!active) return;
        console.error("Failed to fetch jobs:", err);
        if (err instanceof Error && (err as any).response?.status === 400 && matchMode === "matched") {
          setError("Please add skills to your profile or upload a resume to see matched jobs.");
        } else {
          setError("Failed to load jobs. Make sure the backend is running.");
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchJobs();

    return () => {
      active = false;
    };
  }, [searchQuery, filters, page, matchMode, retryCount]);

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setPage(1);
  };

  const handleFilterChange = (key: string, value: string | undefined) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-[#0a0a0f] text-white">
        {/* Gradient orbs background */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-600/20 rounded-full blur-[128px]" />
          <div className="absolute top-1/2 -left-40 w-96 h-96 bg-blue-600/15 rounded-full blur-[128px]" />
          <div className="absolute -bottom-40 right-1/3 w-96 h-96 bg-indigo-600/10 rounded-full blur-[128px]" />
        </div>

        <Navbar />

        <div className="relative z-10">
          {/* Hero Section */}
          <section className="max-w-7xl mx-auto px-4 sm:px-6 pt-10 pb-6">
            <div className="text-center mb-8">
              <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold mb-3">
                Find Your Dream{" "}
                <span className="bg-gradient-to-r from-purple-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                  Data Science
                </span>{" "}
                Job
              </h2>
              <p className="text-gray-400 text-sm sm:text-base max-w-2xl mx-auto mb-8 px-4">
                Real-time jobs matched to your resume and skills
              </p>
              
              <div className="flex justify-center mb-8 px-4">
                <div className="bg-zinc-900/80 p-1 rounded-xl border border-zinc-800 inline-flex w-full max-w-xs sm:w-auto">
                  <button
                    onClick={() => { setMatchMode("all"); setPage(1); }}
                    className={`flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 sm:px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      matchMode === "all" 
                        ? "bg-zinc-800 text-white shadow-sm" 
                        : "text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <Globe className="w-4 h-4" />
                    All Jobs
                  </button>
                  <button
                    onClick={() => { setMatchMode("matched"); setPage(1); }}
                    className={`flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 sm:px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      matchMode === "matched" 
                        ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shadow-sm" 
                        : "text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <Sparkles className="w-4 h-4" />
                    Matched for Me
                  </button>
                </div>
              </div>
            </div>

            {matchMode === "all" && (
              <>
                <SearchBar onSearch={handleSearch} />
                <FilterPills filters={filters} onFilterChange={handleFilterChange} />
              </>
            )}
          </section>

        {/* Results */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 pb-16">
          {/* Result count */}
          <div className="flex items-center justify-between mb-6">
            <p className="text-sm text-gray-400">
              {loading ? "Searching..." : `${total} jobs found`}
            </p>
            {total > 0 && (
              <p className="text-sm text-gray-500">
                Page {page} of {Math.ceil(total / 20)}
              </p>
            )}
          </div>

          {/* Error state */}
          {error && (
            <div className="text-center py-16">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>
              </div>
              <p className="text-gray-400 mb-4">{error}</p>
              <button
                onClick={() => setRetryCount((r) => r + 1)}
                className="px-6 py-2 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {/* Loading skeletons */}
          {loading && !error && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <JobCardSkeleton key={i} />
              ))}
            </div>
          )}

          {/* Job cards */}
          {!loading && !error && jobs.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {jobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          )}

          {/* Empty state */}
          {!loading && !error && jobs.length === 0 && (
            <div className="text-center py-16">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-800 mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
              </div>
              <p className="text-gray-400 text-lg mb-2">No jobs found</p>
              <p className="text-gray-500 text-sm">Try adjusting your search or filters</p>
            </div>
          )}

          {/* Pagination */}
          {!loading && total > 20 && (
            <div className="flex flex-wrap items-center justify-center gap-3 mt-10">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm font-medium hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                ← Previous
              </button>
              <span className="text-sm text-gray-400 px-2">
                Page {page} of {Math.ceil(total / 20)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!hasMore}
                className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm font-medium hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </main>
      </div>
      </div>
    </AuthGuard>
  );
}
