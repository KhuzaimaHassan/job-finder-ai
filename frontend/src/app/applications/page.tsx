"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { Navbar } from "@/components/navbar";
import { getApplications, updateApplication, deleteApplication, type Application } from "@/lib/api";
import { DragDropContext, Droppable, Draggable, DropResult } from "@hello-pangea/dnd";
import { Loader2, Trash2, Calendar, Building, Briefcase } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

const COLUMNS = ["Saved", "Applied", "Interview", "Offer", "Rejected"];

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  // Prevent hydration mismatch for DnD
  const [isBrowser, setIsBrowser] = useState(false);

  useEffect(() => {
    setIsBrowser(true);
    fetchApps();
  }, []);

  const fetchApps = async () => {
    try {
      const data = await getApplications();
      setApplications(data);
    } catch (err) {
      toast.error("Failed to load applications");
    } finally {
      setLoading(false);
    }
  };

  const onDragEnd = async (result: DropResult) => {
    const { destination, source, draggableId } = result;

    if (!destination) return;
    if (destination.droppableId === source.droppableId && destination.index === source.index) {
      return;
    }

    const newStatus = destination.droppableId as Application["status"];
    const draggedAppId = draggableId;

    // Optimistic UI update
    setApplications((prev) => 
      prev.map((app) => 
        app.id === draggedAppId ? { ...app, status: newStatus } : app
      )
    );

    try {
      await updateApplication(draggedAppId, { status: newStatus });
      toast.success(`Moved to ${newStatus}`);
    } catch (err) {
      toast.error("Failed to move application");
      fetchApps(); // Revert on failure
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to remove this application?")) return;
    try {
      await deleteApplication(id);
      setApplications((prev) => prev.filter((a) => a.id !== id));
      toast.success("Application removed");
    } catch (err) {
      toast.error("Failed to remove application");
    }
  };

  if (loading || !isBrowser) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col">
          <Navbar />
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
          </div>
        </div>
      </AuthGuard>
    );
  }

  const appsByStatus = COLUMNS.reduce((acc, col) => {
    acc[col] = applications.filter((app) => app.status === col);
    return acc;
  }, {} as Record<string, Application[]>);

  const stats = {
    total: applications.length,
    applied: applications.filter(a => a.status === 'Applied').length,
    interviews: applications.filter(a => a.status === 'Interview').length,
    offers: applications.filter(a => a.status === 'Offer').length,
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-[1600px] w-full mx-auto px-4 sm:px-6 py-8">
          <div className="mb-8">
            <h1 className="text-xl sm:text-2xl font-bold mb-4">Application Tracker</h1>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl px-4 py-3">
                <p className="text-zinc-400 text-xs font-medium uppercase tracking-wider mb-1">Total</p>
                <p className="text-2xl font-bold text-white">{stats.total}</p>
              </div>
              <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl px-4 py-3">
                <p className="text-indigo-400 text-xs font-medium uppercase tracking-wider mb-1">Applied</p>
                <p className="text-2xl font-bold text-indigo-300">{stats.applied}</p>
              </div>
              <div className="bg-purple-500/10 border border-purple-500/20 rounded-xl px-4 py-3">
                <p className="text-purple-400 text-xs font-medium uppercase tracking-wider mb-1">Interviews</p>
                <p className="text-2xl font-bold text-purple-300">{stats.interviews}</p>
              </div>
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-3">
                <p className="text-emerald-400 text-xs font-medium uppercase tracking-wider mb-1">Offers</p>
                <p className="text-2xl font-bold text-emerald-300">{stats.offers}</p>
              </div>
            </div>
          </div>

          {/* Mobile scroll hint */}
          <p className="text-xs text-zinc-500 mb-3 sm:hidden flex items-center gap-1">
            ← Swipe horizontally to see all columns →
          </p>

          <DragDropContext onDragEnd={onDragEnd}>
            <div className="flex gap-6 overflow-x-auto pb-8 items-start snap-x">
              {COLUMNS.map((col) => (
                <div key={col} className="min-w-[300px] w-[300px] bg-zinc-900/40 border border-zinc-800/80 rounded-xl flex flex-col snap-start">
                  <div className="p-4 border-b border-zinc-800/80 flex items-center justify-between">
                    <h3 className="font-semibold text-zinc-200">{col}</h3>
                    <span className="bg-zinc-800 text-zinc-300 text-xs py-0.5 px-2 rounded-full font-medium">
                      {appsByStatus[col].length}
                    </span>
                  </div>
                  
                  <Droppable droppableId={col}>
                    {(provided, snapshot) => (
                      <div
                        {...provided.droppableProps}
                        ref={provided.innerRef}
                        className={`p-3 min-h-[500px] flex flex-col gap-3 transition-colors ${snapshot.isDraggingOver ? 'bg-zinc-800/20' : ''}`}
                      >
                        {appsByStatus[col].map((app, index) => (
                          <Draggable key={app.id} draggableId={app.id} index={index}>
                            {(provided, snapshot) => (
                              <div
                                ref={provided.innerRef}
                                {...provided.draggableProps}
                                {...provided.dragHandleProps}
                                className={`bg-zinc-950 border border-zinc-800 rounded-lg p-4 group select-none ${
                                  snapshot.isDragging ? 'shadow-2xl shadow-indigo-500/10 border-indigo-500/50 scale-[1.02]' : 'hover:border-zinc-700'
                                } transition-all`}
                                style={{ ...provided.draggableProps.style }}
                              >
                                <div className="flex items-start justify-between mb-2">
                                  <Link href={`/job/${app.job_id}`} className="font-medium text-white hover:text-indigo-400 transition-colors line-clamp-1">
                                    {app.job_title}
                                  </Link>
                                  <button onClick={() => handleDelete(app.id)} className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400 transition-all p-1">
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                </div>
                                <div className="text-xs text-zinc-400 flex items-center gap-1.5 mb-3">
                                  <Building className="w-3.5 h-3.5" />
                                  <span className="line-clamp-1">{app.company}</span>
                                </div>
                                <div className="text-[10px] text-zinc-500 flex items-center gap-1.5 mt-auto pt-3 border-t border-zinc-800/50">
                                  <Calendar className="w-3 h-3" />
                                  {new Date(app.updated_at).toLocaleDateString()}
                                </div>
                              </div>
                            )}
                          </Draggable>
                        ))}
                        {appsByStatus[col].length === 0 && (
                          <div className="flex-1 flex flex-col items-center justify-center text-zinc-600 text-sm italic py-8 border-2 border-dashed border-zinc-800/50 rounded-lg">
                            No jobs {col.toLowerCase()}
                          </div>
                        )}
                        {provided.placeholder}
                      </div>
                    )}
                  </Droppable>
                </div>
              ))}
            </div>
          </DragDropContext>
        </main>
      </div>
    </AuthGuard>
  );
}
