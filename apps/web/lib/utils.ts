import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Deterministic, short initials for avatar display.
 *
 * Prefers up to two words from the display name ("Tejaswani Mishra" -> "TM"),
 * falls back to the email local-part ("tejaswanimishra21@gmail.com" -> "T"),
 * and finally to "U" when nothing usable is available.
 */
export function userInitials(
  displayName: string | null | undefined,
  email: string | null | undefined
): string {
  const source =
    displayName?.trim() || email?.split("@")[0]?.trim() || "";
  const words = source.split(/\s+/).filter(Boolean);
  if (words.length === 0) return "U";
  return words
    .slice(0, 2)
    .map((w) => (Array.from(w)[0] ?? "").toUpperCase())
    .join("");
}
