import { Skeleton } from "@/components/ui/skeleton";

export function JobCardSkeleton() {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <Skeleton className="h-5 w-16 rounded-full bg-white/[0.06]" />
        <Skeleton className="h-3 w-12 bg-white/[0.06]" />
      </div>
      <Skeleton className="h-5 w-4/5 mb-2 bg-white/[0.06]" />
      <Skeleton className="h-4 w-2/5 mb-1 bg-white/[0.06]" />
      <Skeleton className="h-3 w-1/3 mb-3 bg-white/[0.06]" />
      <div className="flex gap-1.5 mb-4">
        <Skeleton className="h-5 w-14 rounded-md bg-white/[0.06]" />
        <Skeleton className="h-5 w-10 rounded-md bg-white/[0.06]" />
        <Skeleton className="h-5 w-16 rounded-md bg-white/[0.06]" />
      </div>
      <Skeleton className="h-3 w-full mb-1 bg-white/[0.06]" />
      <Skeleton className="h-3 w-3/4 mb-4 bg-white/[0.06]" />
      <Skeleton className="h-10 w-full rounded-lg bg-white/[0.06]" />
    </div>
  );
}
