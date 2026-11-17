/**
 * Cirrascale / Qualcomm AI Inference Suite client.
 *
 * Thin wrapper around the text-completions REST endpoint:
 *   POST {BASE_URL}/completions
 *   Authorization: Bearer <CIRRASCALE_API_KEY>
 *   body: { prompt, model, stream, max_tokens }
 *   -> { choices: [{ text }] }
 *
 * This is a *completions* API (single `prompt` string), not a chat/messages API.
 * We build chat-style prompts by hand in `buildPrompt()`.
 *
 * Keep all usage of this module SERVER-SIDE so the API key is never shipped to
 * the browser. See docs/cirrascale-platform.md for the full platform reference.
 */

export const DEFAULT_BASE_URL = "https://aisuite.cirrascale.com/apis/v2";
export const DEFAULT_MODEL = "Llama-3.1-8B";

/** Models known to be available on the free-to-try tier. Update as needed. */
export const KNOWN_MODELS = [
  "Llama-3.1-8B",
  "Llama-3.1-70B",
  "Qwen2.5-7B-Instruct",
] as const;

export interface CompletionOptions {
  model?: string;
  maxTokens?: number;
  stream?: boolean;
}

interface CompletionResponse {
  choices?: Array<{ text?: string }>;
  error?: unknown;
}

function getConfig() {
  const apiKey = process.env.CIRRASCALE_API_KEY;
  const baseUrl = process.env.CIRRASCALE_BASE_URL ?? DEFAULT_BASE_URL;
  const model = process.env.CIRRASCALE_MODEL ?? DEFAULT_MODEL;
  if (!apiKey) {
    throw new Error(
      "CIRRASCALE_API_KEY is not set. Copy .env.example to .env.local and add your key."
    );
  }
  return { apiKey, baseUrl, model };
}

/**
 * Send a raw prompt to the completions endpoint and return the generated text.
 */
export async function complete(
  prompt: string,
  options: CompletionOptions = {}
): Promise<string> {
  const { apiKey, baseUrl, model } = getConfig();

  const res = await fetch(`${baseUrl}/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      prompt,
      model: options.model ?? model,
      stream: options.stream ?? false,
      max_tokens: options.maxTokens ?? 1024,
    }),
    // Planning calls can take a while on larger models.
    cache: "no-store",
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Cirrascale request failed (${res.status}): ${detail}`);
  }

  const data = (await res.json()) as CompletionResponse;
  const text = data.choices?.[0]?.text;
  if (typeof text !== "string") {
    throw new Error("Unexpected Cirrascale response shape (no choices[0].text).");
  }
  return text.trim();
}
