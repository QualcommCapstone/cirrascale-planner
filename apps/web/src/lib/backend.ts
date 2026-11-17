/**
 * Backend selection. Server-only — never imported into a client component.
 *
 * When BACKEND_URL is set, the app's API routes proxy to the FastAPI backend
 * (apps/api). When it's unset, they use the in-Next pipeline (the existing
 * Cirrascale + Wikipedia path), so nothing breaks until the backend is wired
 * end-to-end. Switching is a config change, not a code change.
 */
export function getBackendUrl(): string | null {
  const url = process.env.BACKEND_URL?.trim();
  return url ? url.replace(/\/$/, "") : null;
}
