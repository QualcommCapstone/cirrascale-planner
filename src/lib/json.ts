/**
 * Best-effort JSON extraction from an LLM completion.
 *
 * Models wrap JSON in prose or ```json fences, or emit trailing text. This pulls
 * the first balanced {...} object and parses it. Returns null if nothing parses.
 */
export function extractJson<T = unknown>(raw: string): T | null {
  if (!raw) return null;
  const text = raw.trim();

  // Prefer a fenced block if there is one, but fall back to the whole text:
  // models often emit a stray ``` after the JSON, which makes the "fence"
  // capture trailing prose instead.
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidates = fence ? [fence[1].trim(), text] : [text];
  for (const c of candidates) {
    const found = parseFirstObject<T>(c);
    if (found !== null) return found;
  }
  return null;
}

function parseFirstObject<T>(text: string): T | null {
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

/**
 * Salvage the complete objects of an array from possibly truncated JSON.
 *
 * Llama-3.1-8B sometimes never closes an array: it repeats its items until it
 * hits max_tokens, so the whole document never parses. Given the array's key
 * (e.g. "days"), this returns every fully-closed `{...}` item inside it.
 */
export function extractArrayItems<T = unknown>(raw: string, key: string): T[] {
  const m = new RegExp(String.raw`"${key}"\s*:\s*\[`).exec(raw ?? "");
  if (!m) return [];
  const items: T[] = [];
  let depth = 0;
  let start = -1;
  let inStr = false;
  let esc = false;
  for (let i = m.index + m[0].length; i < raw.length; i++) {
    const ch = raw[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === "\\") esc = true;
      else if (ch === '"') inStr = false;
      continue;
    }
    if (ch === '"') inStr = true;
    else if (ch === "{") {
      if (depth === 0) start = i;
      depth++;
    } else if (ch === "}") {
      depth--;
      if (depth === 0 && start !== -1) {
        try {
          items.push(JSON.parse(raw.slice(start, i + 1)) as T);
        } catch {
          // skip a malformed item, keep going
        }
        start = -1;
      }
      if (depth < 0) break;
    } else if (ch === "]" && depth === 0) break; // array closed normally
  }
  return items;
}
