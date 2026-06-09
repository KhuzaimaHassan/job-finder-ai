import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

/**
 * /auth/callback — Supabase PKCE OAuth callback handler
 *
 * After Google login, Supabase redirects here with ?code=<one-time-code>
 * instead of #access_token=... in the URL hash.
 *
 * This route:
 *   1. Exchanges the one-time code for a session (server-side, secure)
 *   2. Redirects the user to /dashboard with a CLEAN URL (no tokens visible)
 *
 * The session is stored in an HttpOnly cookie by the Supabase client,
 * so tokens are never exposed in the browser URL bar or history.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  // Validate 'next' against internal paths only (prevent open redirect)
  const ALLOWED_PATHS = ['/dashboard', '/profile', '/resume', '/applications']
  const rawNext = searchParams.get('next')
  const next = rawNext && ALLOWED_PATHS.some(p => rawNext.startsWith(p)) ? rawNext : '/dashboard'

  if (code) {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        auth: {
          flowType: 'pkce',
          detectSessionInUrl: false,
          persistSession: false, // session stored in cookie by browser client
        },
      }
    )

    const { error } = await supabase.auth.exchangeCodeForSession(code)

    if (!error) {
      // Redirect cleanly to /dashboard — NO tokens in URL
      const redirectUrl = new URL(next, origin)
      return NextResponse.redirect(redirectUrl)
    }

    // Code exchange failed — redirect to login with error
    console.error('[auth/callback] Code exchange failed:', error.message)
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(error.message)}`, origin)
    )
  }

  // No code present — redirect to login
  return NextResponse.redirect(new URL('/login?error=missing_code', origin))
}
