/**
 * OpenUI system prompt (server-side).
 *
 * Describes the component library the model may emit. Built here rather than in
 * the browser so /api/chat never accepts a client-supplied prompt.
 */
import { generateSystemPrompt } from "@openuidev/lang-core";
import { openuiLibrary, openuiPromptOptions } from "@openuidev/react-ui";

let cached: string | null = null;

export function getOpenUiSystemPrompt(): string {
  if (!cached) {
    cached = generateSystemPrompt({
      library: openuiLibrary.toSpec(),
      promptOptions: openuiPromptOptions,
    });
  }
  return cached;
}
