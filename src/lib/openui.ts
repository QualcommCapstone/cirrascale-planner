/**
 * OpenUI system prompt (server-side).
 *
 * Describes the component library the model may emit. Built here rather than in
 * the browser so /api/chat never accepts a client-supplied prompt.
 *
 * Only the handful of components a stop panel needs are described (the full
 * library is ~80 components / ~9k tokens), with one example shaped like the
 * panel we want. The client still renders with the full library.
 */
import { generateSystemPrompt } from "@openuidev/lang-core";
import { openuiLibrary } from "@openuidev/react-ui";

const PANEL_COMPONENTS = [
  "Stack",
  "Card",
  "CardHeader",
  "TextContent",
  "ListBlock",
  "ListItem",
  "TagBlock",
  "Separator",
];

const PANEL_EXAMPLE = `Example — trip stop panel:

root = Stack([card])
card = Card([header, overview, list])
header = CardHeader("Lisbon, Portugal", "Days 1–2")
overview = TextContent("Hilly old town of tiled facades and riverside viewpoints.")
list = ListBlock([a1, a2])
a1 = ListItem("Alfama walk", "Wander the oldest district's steep lanes and lookouts.")
a2 = ListItem("Pastéis de Belém", "Try the original custard tarts near the monastery.")`;

const PANEL_RULES = [
  "Use only the components listed above.",
  "Never use images or image URLs.",
  "Use only the activities you are given, in the given order. Do not add, rename, or drop any.",
  "Output OpenUI Lang only: no code fences, no explanation before or after.",
];

let cached: string | null = null;

export function getOpenUiSystemPrompt(): string {
  if (!cached) {
    const spec = openuiLibrary.toSpec();
    cached = generateSystemPrompt({
      library: {
        root: spec.root,
        components: Object.fromEntries(
          PANEL_COMPONENTS.map((name) => [name, spec.components[name]])
        ),
      },
      promptOptions: { examples: [PANEL_EXAMPLE], additionalRules: PANEL_RULES },
    });
  }
  return cached;
}
