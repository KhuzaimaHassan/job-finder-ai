import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function safeExternalUrl(value: string): string | null {
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}

export function postedDateLabel(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleDateString() : value;
}

/**
 * Cleans up broken text encodings often found in scraped job descriptions.
 * Fixes common Windows-1252 to UTF-8 mojibake issues.
 */
export function cleanJobDescription(text: string) {
  if (!text) return "";
  return text
    .replace(/â€“/g, "–")
    .replace(/â€”/g, "—")
    .replace(/â€™/g, "'")
    .replace(/â€œ/g, '"')
    .replace(/â€ /g, '"')
    .replace(/â€¦/g, "…")
    .replace(/â/g, "-"); // fallback for loose 'â' dashes
}
