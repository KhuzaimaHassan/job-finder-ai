import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
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
