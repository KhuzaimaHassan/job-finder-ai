"use client";

import { useAuth } from "@/contexts/auth-context";
import { BriefcaseBusiness, FileText, UserCircle, LogOut, Menu, X, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

export function Navbar() {
  const { user, signOut } = useAuth();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
    { name: "Applications", path: "/applications", icon: BriefcaseBusiness },
    { name: "Resume", path: "/resume", icon: FileText },
    { name: "Profile", path: "/profile", icon: UserCircle },
  ];

  return (
    <nav className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur-md sticky top-0 z-50">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 justify-between items-center">
          {/* Left: Logo + hamburger + desktop nav */}
          <div className="flex items-center gap-6 min-w-0">
            {/* Hamburger — mobile only */}
            <button
              className="md:hidden p-1.5 text-zinc-400 hover:text-white rounded-md hover:bg-zinc-800 transition-colors"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>

            {/* Logo */}
            <Link href="/dashboard" className="flex items-center gap-2 shrink-0">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400">
                <BriefcaseBusiness className="h-5 w-5" />
              </div>
              <span className="text-lg font-bold tracking-tight text-zinc-100 hidden xs:inline sm:inline">
                JobFinder <span className="text-indigo-400">AI</span>
              </span>
            </Link>

            {/* Desktop nav */}
            <div className="hidden md:flex items-center space-x-1">
              {navItems.map((item) => {
                const isActive = pathname === item.path;
                return (
                  <Link
                    key={item.name}
                    href={item.path}
                    className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-zinc-800 text-zinc-100"
                        : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
                    }`}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.name}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Right: User menu */}
          <div className="flex items-center gap-3 shrink-0">
            {user && (
              <div className="relative">
                <button
                  onClick={() => setMenuOpen(!menuOpen)}
                  className="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900 p-1 sm:pr-3 transition-colors hover:border-zinc-700 focus:outline-none"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-white text-sm font-bold shrink-0">
                    {user.email?.charAt(0).toUpperCase() || "U"}
                  </div>
                  <span className="hidden sm:inline text-sm font-medium text-zinc-300 max-w-[100px] truncate">
                    {user.user_metadata?.full_name?.split(" ")[0] || user.email?.split("@")[0]}
                  </span>
                </button>

                {menuOpen && (
                  <>
                    {/* Backdrop to close */}
                    <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
                    <div className="absolute right-0 mt-2 w-48 origin-top-right rounded-xl border border-zinc-800 bg-zinc-900 py-1 shadow-lg z-20">
                      <p className="px-4 py-2 text-xs text-zinc-500 truncate border-b border-zinc-800 mb-1">
                        {user.email}
                      </p>
                      <button
                        onClick={() => { setMenuOpen(false); signOut(); }}
                        className="flex w-full items-center gap-2 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 transition-colors"
                      >
                        <LogOut className="h-4 w-4" />
                        Sign out
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-zinc-800 bg-zinc-900/95 backdrop-blur-md px-4 py-3 space-y-1 overflow-y-auto max-h-[80vh]">
          {navItems.map((item) => (
            <Link
              key={item.name}
              href={item.path}
              onClick={() => setMobileMenuOpen(false)}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                pathname === item.path
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
              }`}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}
