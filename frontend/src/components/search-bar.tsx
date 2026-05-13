"use client";

import { useState, useRef } from "react";
import { Input } from "@/components/ui/input";

export function SearchBar({ onSearch }: { onSearch: (query: string) => void }) {
  const [value, setValue] = useState("");
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setValue(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => onSearch(v), 400);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (debounceRef.current) clearTimeout(debounceRef.current);
    onSearch(value);
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl mx-auto mb-6 px-0">
      <div className="relative group">
        {/* Glow ring */}
        <div className="absolute -inset-0.5 bg-gradient-to-r from-purple-600/30 to-blue-600/30 rounded-xl blur-sm opacity-0 group-focus-within:opacity-100 transition-opacity duration-300" />
        <div className="relative flex items-center bg-white/[0.04] border border-white/[0.08] rounded-xl overflow-hidden group-focus-within:border-purple-500/40 transition-colors">
          <div className="pl-3 text-gray-500 shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 sm:w-5 sm:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          </div>
          <Input
            type="text"
            value={value}
            onChange={handleChange}
            placeholder="Search jobs... e.g. python, AI, data science"
            className="border-0 bg-transparent text-white placeholder:text-gray-500 text-sm sm:text-base py-3 sm:py-4 pl-2 pr-2 focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:outline-none min-w-0"
            id="job-search-input"
          />
          <button
            type="submit"
            className="mr-2 px-3 sm:px-5 py-1.5 sm:py-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium hover:from-purple-500 hover:to-blue-500 transition-all shrink-0 whitespace-nowrap"
          >
            Search
          </button>
        </div>
      </div>
    </form>
  );
}
