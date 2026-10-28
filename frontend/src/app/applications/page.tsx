"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { Navbar } from "@/components/navbar";
import { getApplications, updateApplication, deleteApplication, type Application } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { DragDropContext, Droppable, Draggable, type DropResult, type DraggableProvidedDragHandleProps } from "@hello-pangea/dnd";
import { Loader2, Trash2, Building, GripVertical, NotebookPen, X } from "lucide-react";

const COLUMNS: Application["status"][] = ["Saved", "Applied", "Interview", "Offer", "Rejected"];
const CONTROL = "min-h-11 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200";

function ApplicationCard({ app, disabled, handle, onStatus, onNotes, onDelete }: {
  app: Application; disabled: boolean; handle?: DraggableProvidedDragHandleProps | null;
  onStatus: (id: string, status: Application["status"]) => void;
  onNotes: (app: Application) => void; onDelete: (id: string) => void;
}) {
  return <article className="min-w-0 space-y-3 rounded-xl border border-zinc-800 bg-zinc-950 p-4">
    <div className="flex min-w-0 items-start gap-2">
      {handle && <button {...handle} aria-label={`Drag ${app.job_title}`} className="flex h-11 w-8 shrink-0 items-center justify-center rounded text-zinc-500 hover:text-white"><GripVertical className="h-5 w-5" /></button>}
      <div className="min-w-0 flex-1 pt-2"><Link href={`/job/${encodeURIComponent(app.job_id)}`} className="break-words font-medium leading-relaxed text-white hover:text-indigo-300">{app.job_title}</Link><p className="mt-2 flex items-start gap-1.5 text-xs text-zinc-400"><Building className="h-3.5 w-3.5 shrink-0" /><span className="break-words">{app.company}</span></p></div>
      <button type="button" aria-label={`Remove ${app.job_title}`} disabled={disabled} onClick={() => onDelete(app.id)} className="flex h-11 w-9 shrink-0 items-center justify-center rounded-lg text-zinc-500 hover:bg-red-500/10 hover:text-red-300 disabled:opacity-40"><Trash2 className="h-4 w-4" /></button>
    </div>
    <label className="block text-xs text-zinc-400">Status
      <select aria-label={`Status for ${app.job_title}`} value={app.status} disabled={disabled} onChange={e => onStatus(app.id, e.target.value as Application["status"])} className={`${CONTROL} mt-1 w-full`}>
        {COLUMNS.map(status => <option key={status}>{status}</option>)}
      </select>
    </label>
    {app.notes && <p className="line-clamp-3 whitespace-pre-wrap break-words text-sm leading-relaxed text-zinc-400">{app.notes}</p>}
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800 pt-2">
      <button type="button" onClick={() => onNotes(app)} disabled={disabled} className="flex min-h-11 items-center gap-1.5 rounded-lg px-2 text-sm text-indigo-300 hover:bg-indigo-500/10"><NotebookPen className="h-4 w-4" />{app.notes ? "Edit notes" : "Add notes"}</button>
      <time dateTime={app.updated_at} className="text-xs text-zinc-500">Updated {new Date(app.updated_at).toLocaleDateString()}</time>
    </div>
  </article>;
}

function ApplicationsContent() {
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const busy = useRef(false);
  const [mobileStage, setMobileStage] = useState("All stages");
  const [editing, setEditing] = useState<{ app: Application; notes: string } | null>(null);
  const notesDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let active = true;
    void getApplications().then(data => { if (active) setApps(data); })
      .catch(err => { if (active) setError(apiErrorMessage(err, "Could not load your applications. Please try again.")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);

  const hasEditor = editing !== null;
  useEffect(() => {
    if (!hasEditor) return;
    const dialog = notesDialog.current;
    const previousOverflow = document.body.style.overflow;
    dialog?.showModal(); document.body.style.overflow = "hidden";
    return () => { dialog?.close(); document.body.style.overflow = previousOverflow; };
  }, [hasEditor]);

  const changeStatus = async (id: string, status: Application["status"]) => {
    if (busy.current) return;
    busy.current = true; setBusyId(id); setError(null);
    const previous = apps;
    setApps(current => current.map(app => app.id === id ? { ...app, status } : app));
    try { const saved = await updateApplication(id, { status }); setApps(current => current.map(app => app.id === id ? saved : app)); }
    catch (err) { setApps(previous); setError(apiErrorMessage(err, "Could not move this application. Please try again.")); }
    finally { busy.current = false; setBusyId(null); }
  };
  const onDragEnd = ({ destination, source, draggableId }: DropResult) => {
    if (!destination || destination.droppableId === source.droppableId) return;
    void changeStatus(draggableId, destination.droppableId as Application["status"]);
  };
  const remove = async (id: string) => {
    if (busy.current || !confirm("Remove this application and its notes?")) return;
    busy.current = true; setBusyId(id); setError(null);
    try { await deleteApplication(id); setApps(current => current.filter(app => app.id !== id)); }
    catch (err) { setError(apiErrorMessage(err, "Could not remove this application. Please try again.")); }
    finally { busy.current = false; setBusyId(null); }
  };
  const saveNotes = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editing || busy.current) return;
    busy.current = true; setBusyId(editing.app.id); setError(null);
    try { const saved = await updateApplication(editing.app.id, { notes: editing.notes }); setApps(current => current.map(app => app.id === saved.id ? saved : app)); setEditing(null); }
    catch (err) { setError(apiErrorMessage(err, "Could not save your notes. Your draft is still here.")); }
    finally { busy.current = false; setBusyId(null); }
  };
  const cardProps = { disabled: busyId !== null, onStatus: changeStatus, onNotes: (app: Application) => { setError(null); setEditing({ app, notes: app.notes || "" }); }, onDelete: remove };
  const visibleApps = mobileStage === "All stages" ? apps : apps.filter(app => app.status === mobileStage);

  return <div className="min-h-screen min-w-0 bg-[#0a0a0f] text-white">
    <Navbar />
    <main id="main-content" className="mx-auto w-full min-w-0 max-w-[1600px] px-4 py-8 sm:px-6">
      <h1 className="mb-2 text-2xl font-bold sm:text-3xl">Application Tracker</h1><p className="mb-6 text-sm text-zinc-400">Keep your progress, next steps, and interview notes in one place.</p>
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[["Total", apps.length], ["Applied", apps.filter(a => a.status === "Applied").length], ["Interviews", apps.filter(a => a.status === "Interview").length], ["Offers", apps.filter(a => a.status === "Offer").length]].map(([label, count]) => <div key={label} className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4"><p className="text-xs text-zinc-400">{label}</p><p className="mt-1 text-2xl font-semibold">{count}</p></div>)}
      </div>
      {error && !editing && <div role="alert" className="mb-5 rounded-xl border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-200"><p>{error}</p><button type="button" className={`${CONTROL} mt-3`} onClick={() => { setError(null); setLoading(true); setRetry(r => r + 1); }}>Retry loading applications</button></div>}
      {loading ? <div role="status" aria-label="Loading applications" className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-indigo-400" /></div> : <>
        {apps.length === 0 && !error && <div className="mb-6 rounded-xl border border-dashed border-zinc-700 p-6 text-center"><p className="mb-3 text-zinc-400">Your tracker is ready. Save a job to get started.</p><Link href="/dashboard" className="inline-flex min-h-11 items-center rounded-lg bg-indigo-600 px-5 text-sm font-medium">Browse jobs</Link></div>}
        <div className="md:hidden"><label htmlFor="mobile-stage" className="mb-2 block text-sm text-zinc-300">Filter by stage</label><select id="mobile-stage" value={mobileStage} onChange={e => setMobileStage(e.target.value)} className={`${CONTROL} mb-4 w-full`}>{["All stages", ...COLUMNS].map(s => <option key={s}>{s}</option>)}</select><div className="space-y-4">{visibleApps.map(app => <ApplicationCard key={app.id} app={app} {...cardProps} />)}{visibleApps.length === 0 && apps.length > 0 && <p className="py-8 text-center text-sm text-zinc-500">No applications in this stage.</p>}</div></div>
        <div className="hidden min-w-0 md:block"><p className="mb-3 text-xs text-zinc-500">Drag the handle to move a card, or use its status menu. Scroll the board to see all stages.</p><DragDropContext onDragEnd={onDragEnd}><div aria-label="Application stages" role="region" tabIndex={0} className="flex min-w-0 gap-4 overflow-x-auto overscroll-x-contain pb-5">
          {COLUMNS.map(status => <section key={status} aria-label={`${status} applications`} className="w-72 shrink-0 rounded-xl border border-zinc-800 bg-zinc-900/40"><div className="flex items-center justify-between border-b border-zinc-800 p-4"><h2 className="text-sm font-semibold">{status}</h2><span className="text-xs text-zinc-400">{apps.filter(app => app.status === status).length}</span></div><Droppable droppableId={status}>{(provided, snapshot) => <div ref={provided.innerRef} {...provided.droppableProps} className={`min-h-72 space-y-3 p-3 ${snapshot.isDraggingOver ? "bg-indigo-500/5" : ""}`}>
            {apps.filter(app => app.status === status).map((app, index) => <Draggable key={app.id} draggableId={app.id} index={index} isDragDisabled={busyId !== null} disableInteractiveElementBlocking>{provided => <div ref={provided.innerRef} {...provided.draggableProps} style={provided.draggableProps.style}><ApplicationCard app={app} handle={provided.dragHandleProps} {...cardProps} /></div>}</Draggable>)}{provided.placeholder}
          </div>}</Droppable></section>)}
        </div></DragDropContext></div>
      </>}
      <p role="status" aria-live="polite" className="sr-only">{busyId ? "Saving changes" : "Changes saved"}</p>
      <dialog ref={notesDialog} aria-labelledby="notes-title" onClose={e => { if (!e.currentTarget.open) setEditing(null); }} className="m-auto w-[calc(100%-2rem)] max-w-lg max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-950 p-4 text-white backdrop:bg-black/70 sm:p-6">
        {editing && <form onSubmit={saveNotes} className="space-y-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><h2 id="notes-title" className="text-lg font-semibold">Application notes</h2><p className="mt-1 break-words text-sm text-zinc-400">{editing.app.job_title}</p></div><button type="button" aria-label="Close notes" onClick={() => setEditing(null)} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-zinc-900"><X className="h-5 w-5" /></button></div><label htmlFor="application-notes" className="block text-sm text-zinc-300">Notes and next steps</label><textarea id="application-notes" maxLength={6000} rows={7} value={editing.notes} onChange={e => setEditing({ ...editing, notes: e.target.value })} className="w-full min-w-0 resize-y rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-base" /><p className="text-right text-xs text-zinc-500">{editing.notes.length}/6000</p>{error && <p role="alert" className="text-sm text-red-300">{error}</p>}<button type="submit" disabled={busyId !== null} className="min-h-11 w-full rounded-lg bg-indigo-600 px-5 py-3 text-sm font-medium disabled:opacity-50">{busyId ? "Saving…" : "Save notes"}</button></form>}
      </dialog>
    </main>
  </div>;
}

export default function ApplicationsPage() { return <AuthGuard><ApplicationsContent /></AuthGuard>; }
