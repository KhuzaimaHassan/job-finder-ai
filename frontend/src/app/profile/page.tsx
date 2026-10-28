"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { Navbar } from "@/components/navbar";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { Loader2, Save, CheckCircle, Plus, X } from "lucide-react";

const INPUT = "min-h-11 w-full min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-base text-white";
type Profile = { name: string; location: string; experience_years: number; skills: string[]; target_roles: string[] };

function TagsEditor({ label, values, onChange }: { label: string; values: string[]; onChange: (values: string[]) => void }) {
  const [draft, setDraft] = useState("");
  const id = label === "Skills" ? "profile-skills" : "profile-roles";
  const add = () => {
    const value = draft.trim();
    if (value && !values.some(v => v.toLowerCase() === value.toLowerCase())) onChange([...values, value]);
    setDraft("");
  };
  return <fieldset className="min-w-0 space-y-3">
    <legend className="font-medium text-zinc-200">{label}</legend>
    <div className="flex flex-wrap gap-2">
      {values.length === 0 && <p className="text-sm text-zinc-500">No {label.toLowerCase()} added yet.</p>}
      {values.map(value => <span key={value} className="inline-flex max-w-full items-center gap-1 rounded-lg border border-indigo-500/25 bg-indigo-500/10 pl-3 text-sm text-indigo-200">
        <span className="min-w-0 break-words">{value}</span>
        <button type="button" aria-label={`Remove ${value}`} onClick={() => onChange(values.filter(v => v !== value))} className="flex h-11 w-10 shrink-0 items-center justify-center rounded-lg hover:bg-indigo-500/15"><X className="h-4 w-4" /></button>
      </span>)}
    </div>
    <label htmlFor={id} className="sr-only">Add {label.toLowerCase()}</label>
    <div className="flex min-w-0 gap-2">
      <input id={id} maxLength={100} value={draft} onChange={e => setDraft(e.target.value)} placeholder={`Add ${label === "Skills" ? "a skill, e.g. Python" : "a role, e.g. Data Scientist"}`} className={INPUT}
        onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
      <button type="button" aria-label={`Add ${label === "Skills" ? "skill" : "role"}`} onClick={add} disabled={!draft.trim()} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-zinc-800 disabled:opacity-40"><Plus className="h-5 w-5" /></button>
    </div>
  </fieldset>;
}

function ProfileContent() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    let active = true;
    void api.get("/api/profile").then(({ data }) => {
      if (active) setProfile({ name: data.name || "", location: data.location || "", experience_years: data.experience_years || 0, skills: data.skills || [], target_roles: data.target_roles || [] });
    }).catch(err => { if (active) setError(apiErrorMessage(err, "Could not load your profile. Please try again.")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!profile || saving) return;
    setSaving(true); setSuccess(false); setError(null);
    try { await api.patch("/api/profile", profile); setSuccess(true); }
    catch (err) { setError(apiErrorMessage(err, "Your changes could not be saved. Please try again.")); }
    finally { setSaving(false); }
  };

  return <div className="min-h-screen bg-[#0a0a0f] text-white">
    <Navbar />
    <main id="main-content" className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
      <form onSubmit={save} className="min-w-0">
        <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0"><h1 className="mb-2 text-2xl font-bold sm:text-3xl">Your Profile</h1><p className="text-sm leading-relaxed text-zinc-400 sm:text-base">Tell us about your skills and the roles you want next.</p></div>
          <button type="submit" disabled={saving || loading || !profile} className="flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 font-medium hover:bg-indigo-500 disabled:opacity-50">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
        {error && <div role="alert" className="mb-5 rounded-lg border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-200"><p>{error}</p>{!profile && <button type="button" className="mt-3 min-h-11 rounded bg-zinc-800 px-4" onClick={() => { setError(null); setLoading(true); setRetry(r => r + 1); }}>Retry loading profile</button>}</div>}
        {success && <p role="status" className="mb-5 flex items-center gap-2 rounded-lg bg-emerald-500/10 p-4 text-sm text-emerald-300"><CheckCircle className="h-4 w-4" />Profile saved successfully</p>}
        {loading ? <div role="status" aria-label="Loading profile" className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-indigo-400" /></div> : profile && <div className="min-w-0 space-y-7 rounded-2xl border border-zinc-800 bg-zinc-900/50 p-4 sm:p-8">
          <div className="grid min-w-0 gap-5 sm:grid-cols-2">
            <div className="min-w-0 space-y-2"><label htmlFor="profile-name" className="text-sm text-zinc-300">Full Name</label><input id="profile-name" autoComplete="name" maxLength={200} className={INPUT} value={profile.name} onChange={e => { setProfile({ ...profile, name: e.target.value }); setSuccess(false); }} /></div>
            <div className="min-w-0 space-y-2"><label htmlFor="profile-location" className="text-sm text-zinc-300">Location</label><input id="profile-location" autoComplete="address-level2" placeholder="Karachi, Pakistan" maxLength={200} className={INPUT} value={profile.location} onChange={e => { setProfile({ ...profile, location: e.target.value }); setSuccess(false); }} /></div>
          </div>
          <div className="space-y-2"><label htmlFor="profile-years" className="text-sm text-zinc-300">Years of Experience</label><input id="profile-years" type="number" min={0} max={50} step={1} className={`${INPUT} sm:max-w-32`} value={profile.experience_years} onChange={e => { setProfile({ ...profile, experience_years: Number(e.target.value) }); setSuccess(false); }} /></div>
          <TagsEditor label="Target Roles" values={profile.target_roles} onChange={target_roles => { setProfile({ ...profile, target_roles }); setSuccess(false); }} />
          <TagsEditor label="Skills" values={profile.skills} onChange={skills => { setProfile({ ...profile, skills }); setSuccess(false); }} />
          <p className="text-sm leading-relaxed text-zinc-400">Resume uploads add skills to your profile. Your experience and target roles stay as you entered them.</p>
        </div>}
      </form>
    </main>
  </div>;
}

export default function ProfilePage() { return <AuthGuard><ProfileContent /></AuthGuard>; }
