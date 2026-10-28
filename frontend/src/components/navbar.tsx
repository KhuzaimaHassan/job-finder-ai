"use client";

import { useAuth } from "@/contexts/auth-context";
import { BriefcaseBusiness, FileText, UserCircle, LogOut, Menu, X, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

const NAV_ITEMS = [
  { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { name: "Applications", path: "/applications", icon: BriefcaseBusiness },
  { name: "Resume", path: "/resume", icon: FileText },
  { name: "Profile", path: "/profile", icon: UserCircle },
];

export function Navbar() {
  const { user, signOut } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);
  const accountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const dismiss = (event: PointerEvent) => {
      if (!accountRef.current?.contains(event.target as Node)) setAccountOpen(false);
      if (!navRef.current?.contains(event.target as Node)) setMobileOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setMobileOpen(false); setAccountOpen(false); }
    };
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", dismiss); document.removeEventListener("keydown", escape); };
  }, []);

  const navLinks = (mobile: boolean) => NAV_ITEMS.map(({ name, path, icon: Icon }) => (
    <Link key={path} href={path} aria-current={pathname === path ? "page" : undefined}
      onClick={() => setMobileOpen(false)}
      className={`flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${mobile ? "w-full" : ""} ${pathname === path ? "bg-zinc-800 text-white" : "text-zinc-400 hover:bg-zinc-800/60 hover:text-white"}`}>
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />{name}
    </Link>
  ));

  return (
    <nav ref={navRef} aria-label="Main navigation" className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur-md">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-indigo-600 focus:p-3 focus:text-white">Skip to content</a>
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-2 px-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-2 sm:gap-4">
          <button type="button" aria-label={mobileOpen ? "Close navigation" : "Open navigation"} aria-expanded={mobileOpen} aria-controls="mobile-navigation"
            onClick={() => { setMobileOpen(!mobileOpen); setAccountOpen(false); }}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-zinc-300 hover:bg-zinc-800 lg:hidden">
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <Link href="/dashboard" aria-label="JobFinder AI dashboard" className="flex min-w-0 items-center gap-2 text-base font-bold tracking-tight text-white sm:text-lg">
            <BriefcaseBusiness className="h-8 w-8 shrink-0 rounded-lg bg-indigo-500/15 p-1.5 text-indigo-400" aria-hidden="true" />
            <span className="whitespace-nowrap">JobFinder <span className="text-indigo-400">AI</span></span>
          </Link>
          <div className="hidden items-center gap-1 lg:flex">{navLinks(false)}</div>
        </div>
        {user && <div ref={accountRef} className="relative shrink-0">
          <button type="button" aria-label="Account options" aria-expanded={accountOpen} aria-controls="account-options"
            onClick={() => { setAccountOpen(!accountOpen); setMobileOpen(false); }}
            className="flex min-h-11 items-center gap-2 rounded-full border border-zinc-800 p-1 sm:pr-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-sm font-semibold text-white" aria-hidden="true">{user.email?.charAt(0).toUpperCase() || "U"}</span>
            <span className="hidden max-w-28 truncate text-sm text-zinc-300 sm:block">{user.user_metadata?.full_name?.split(" ")[0] || user.email?.split("@")[0]}</span>
          </button>
          {accountOpen && <div id="account-options" className="absolute right-0 mt-2 w-60 max-w-[calc(100vw-2rem)] rounded-xl border border-zinc-800 bg-zinc-900 p-2 shadow-xl">
            <p className="break-all border-b border-zinc-800 px-2 py-3 text-xs text-zinc-400">{user.email}</p>
            <button type="button" onClick={async () => { try { await signOut(); setAccountOpen(false); } catch { toast.error("Could not sign out. Please try again."); } }}
              className="flex min-h-11 w-full items-center gap-2 rounded-lg px-2 text-sm text-zinc-200 hover:bg-zinc-800"><LogOut className="h-4 w-4" />Sign out</button>
          </div>}
        </div>}
      </div>
      {mobileOpen && <div id="mobile-navigation" className="max-h-[calc(100dvh-4rem)] overflow-y-auto border-t border-zinc-800 px-3 py-2 lg:hidden">{navLinks(true)}</div>}
    </nav>
  );
}
