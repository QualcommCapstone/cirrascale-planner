/**
 * Best-effort JSON extraction from an LLM completion.
 *
 * Models wrap JSON in prose or ```json fences, or emit trailing text. This pulls
 * the first balanced {...} object and parses it. Returns null if nothing parses.
 */
export function extractJson<T = unknown>(raw: string): T | null {
  if (!raw) return null;

  // Strip code fences if present.
  let text = raw.trim();
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) text = fence[1].trim();

  // Fast path: whole thing parses.
  try {
    return JSON.parse(text) as T;
  } catch {
    // fall through to brace scan
  }

  // Scan for the first balanced top-level object.
  const start = text.indexOf("{");
  if (start === -1) return null;
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === "\\") esc = true;
      else if (ch === '"') inStr = false;
      continue;
    }
    if (ch === '"') inStr = true;
    else if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        const candidate = text.slice(start, i + 1);
        try {
          return JSON.parse(candidate) as T;
        } catch {
          return null;
        }
      }
    }
  }
  return null;
}
