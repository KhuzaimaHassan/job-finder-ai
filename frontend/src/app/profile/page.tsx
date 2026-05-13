"use client";

import { AuthGuard } from "@/components/auth-guard";
import { Navbar } from "@/components/navbar";
import { useState, useEffect } from "react";
import axios from "axios";
import { Loader2, Save, CheckCircle } from "lucide-react";

export default function ProfilePage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  
  const [profile, setProfile] = useState({
    name: "",
    location: "",
    experience_years: 0,
    skills: [] as string[],
    target_roles: [] as string[],
  });

  const [newSkill, setNewSkill] = useState("");
  const [newRole, setNewRole] = useState("");

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const { data } = await axios.get(`${API_URL}/api/profile`);
        setProfile({
          name: data.name || "",
          location: data.location || "",
          experience_years: data.experience_years || 0,
          skills: data.skills || [],
          target_roles: data.target_roles || [],
        });
      } catch (err) {
        console.error("Failed to load profile", err);
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSuccess(false);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      await axios.patch(`${API_URL}/api/profile`, profile);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error("Failed to save profile", err);
    } finally {
      setSaving(false);
    }
  };

  const addSkill = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && newSkill.trim()) {
      e.preventDefault();
      if (!profile.skills.includes(newSkill.trim())) {
        setProfile({ ...profile, skills: [...profile.skills, newSkill.trim()] });
      }
      setNewSkill("");
    }
  };

  const removeSkill = (skillToRemove: string) => {
    setProfile({
      ...profile,
      skills: profile.skills.filter((s) => s !== skillToRemove),
    });
  };

  const addRole = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && newRole.trim()) {
      e.preventDefault();
      if (!profile.target_roles.includes(newRole.trim())) {
        setProfile({ ...profile, target_roles: [...profile.target_roles, newRole.trim()] });
      }
      setNewRole("");
    }
  };

  const removeRole = (roleToRemove: string) => {
    setProfile({
      ...profile,
      target_roles: profile.target_roles.filter((r) => r !== roleToRemove),
    });
  };

  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col">
          <Navbar />
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
          </div>
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-[#0a0a0f] text-white">
        <Navbar />
        
        <main className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold mb-2">Your Profile</h1>
              <p className="text-zinc-400">
                AI matches jobs based on your skills and experience.
              </p>
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Changes
            </button>
          </div>

          {success && (
            <div className="mb-6 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-2 text-emerald-400 text-sm">
              <CheckCircle className="w-4 h-4" />
              Profile saved successfully
            </div>
          )}

          <div className="space-y-8 bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 sm:p-8">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-300">Full Name</label>
                <input
                  type="text"
                  value={profile.name}
                  onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-300">Location (e.g. Karachi, Pakistan)</label>
                <input
                  type="text"
                  value={profile.location}
                  onChange={(e) => setProfile({ ...profile, location: e.target.value })}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Years of Experience</label>
              <input
                type="number"
                min="0"
                max="50"
                value={profile.experience_years}
                onChange={(e) => setProfile({ ...profile, experience_years: parseInt(e.target.value) || 0 })}
                className="w-full sm:w-32 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            <div className="space-y-3">
              <label className="text-sm font-medium text-zinc-300">Target Roles</label>
              <div className="flex flex-wrap gap-2 mb-2">
                {profile.target_roles.map((role) => (
                  <span key={role} className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-blue-500/10 text-blue-300 text-sm border border-blue-500/20">
                    {role}
                    <button onClick={() => removeRole(role)} className="text-blue-400 hover:text-blue-200">×</button>
                  </span>
                ))}
              </div>
              <input
                type="text"
                placeholder="Type a role and press Enter (e.g. Data Scientist)"
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                onKeyDown={addRole}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            <div className="space-y-3">
              <label className="text-sm font-medium text-zinc-300">Skills</label>
              <div className="flex flex-wrap gap-2 mb-2">
                {profile.skills.map((skill) => (
                  <span key={skill} className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-purple-500/10 text-purple-300 text-sm border border-purple-500/20">
                    {skill}
                    <button onClick={() => removeSkill(skill)} className="text-purple-400 hover:text-purple-200">×</button>
                  </span>
                ))}
              </div>
              <input
                type="text"
                placeholder="Type a skill and press Enter (e.g. Python)"
                value={newSkill}
                onChange={(e) => setNewSkill(e.target.value)}
                onKeyDown={addSkill}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <p className="text-xs text-zinc-500">Skills are automatically populated when you upload a resume.</p>
            </div>
          </div>
        </main>
      </div>
    </AuthGuard>
  );
}
