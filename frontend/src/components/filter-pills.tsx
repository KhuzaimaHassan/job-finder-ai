"use client";

const FILTER_OPTIONS = [
  { key: "job_type", value: "remote", label: "🌍 Remote" },
  { key: "location", value: "pakistan", label: "🇵🇰 Pakistan" },
  { key: "location", value: "karachi", label: "📍 Karachi" },
  { key: "location", value: "lahore", label: "📍 Lahore" },
  { key: "location", value: "islamabad", label: "📍 Islamabad" },
  { key: "job_type", value: "fulltime", label: "💼 Full-time" },
  { key: "job_type", value: "parttime", label: "⏰ Part-time" },
  { key: "job_type", value: "internship", label: "🎓 Internship" },
  { key: "source", value: "indeed", label: "Indeed" },
  { key: "source", value: "google", label: "Google Jobs" },
  { key: "source", value: "remoteok", label: "RemoteOK" },
  { key: "source", value: "remotive", label: "Remotive" },
];

interface FilterPillsProps {
  filters: Record<string, string | undefined>;
  onFilterChange: (key: string, value: string | undefined) => void;
}

export function FilterPills({ filters, onFilterChange }: FilterPillsProps) {
  const isActive = (key: string, value: string) => filters[key] === value;

  const handleClick = (key: string, value: string) => {
    if (isActive(key, value)) {
      onFilterChange(key, undefined);
    } else {
      onFilterChange(key, value);
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-center gap-2 max-w-3xl mx-auto mb-8">
      {FILTER_OPTIONS.map(({ key, value, label }) => {
        const active = isActive(key, value);
        return (
          <button
            key={`${key}-${value}`}
            onClick={() => handleClick(key, value)}
            className={`px-3.5 py-1.5 rounded-full text-sm font-medium border transition-all duration-200 ${
              active
                ? "bg-purple-600/20 border-purple-500/50 text-purple-300 shadow-lg shadow-purple-500/10"
                : "bg-white/[0.03] border-white/[0.08] text-gray-400 hover:bg-white/[0.06] hover:border-white/[0.15] hover:text-gray-300"
            }`}
          >
            {label}
          </button>
        );
      })}

      {/* Clear all */}
      {Object.values(filters).some(Boolean) && (
        <button
          onClick={() => {
            onFilterChange("job_type", undefined);
            onFilterChange("location", undefined);
            onFilterChange("source", undefined);
          }}
          className="px-3.5 py-1.5 rounded-full text-sm font-medium text-red-400/70 hover:text-red-400 transition-colors"
        >
          ✕ Clear
        </button>
      )}
    </div>
  );
}
