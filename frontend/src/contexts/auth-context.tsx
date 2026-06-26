"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { User, Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import axios from "axios";
import { api } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      
      // Set default auth header for axios and api if session exists
      if (session?.access_token) {
        axios.defaults.headers.common["Authorization"] = `Bearer ${session.access_token}`;
        api.defaults.headers.common["Authorization"] = `Bearer ${session.access_token}`;
      } else {
        delete axios.defaults.headers.common["Authorization"];
        delete api.defaults.headers.common["Authorization"];
      }
      
      setLoading(false);
    });

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setUser(session?.user ?? null);
      
      // Update axios and api default header
      if (session?.access_token) {
        axios.defaults.headers.common["Authorization"] = `Bearer ${session.access_token}`;
        api.defaults.headers.common["Authorization"] = `Bearer ${session.access_token}`;
      } else {
        delete axios.defaults.headers.common["Authorization"];
        delete api.defaults.headers.common["Authorization"];
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  const signInWithGoogle = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        // Redirect directly to /dashboard.
        // Supabase client will automatically detect the ?code= in the URL,
        // exchange it for a session, and store it securely in local storage.
        redirectTo: `${window.location.origin}/dashboard`,
      },
    });
  };

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider
      value={{ user, session, loading, signInWithGoogle, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
