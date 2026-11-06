import { describe, it, expect } from "vitest";
import { extractJson } from "@/lib/json";

describe("extractJson", () => {
  it("parses a plain JSON object", () => {
    expect(extractJson('{"a":1,"b":"x"}')).toEqual({ a: 1, b: "x" });
  });

  it("parses JSON inside ```json fences", () => {
    const raw = 'Sure!\n```json\n{"ok":true}\n```\nhope that helps';
    expect(extractJson(raw)).toEqual({ ok: true });
  });

  it("extracts the first balanced object from surrounding prose", () => {
    const raw = 'Here you go: {"name":"Tokyo","lat":35.6} — enjoy!';
    expect(extractJson(raw)).toEqual({ name: "Tokyo", lat: 35.6 });
  });

  it("handles braces inside string values", () => {
    const raw = '{"note":"use {curly} braces","n":2}';
    expect(extractJson(raw)).toEqual({ note: "use {curly} braces", n: 2 });
  });

  it("returns null when there is no JSON object", () => {
    expect(extractJson("no json here")).toBeNull();
    expect(extractJson("")).toBeNull();
  });

  it("returns null for an unbalanced / invalid object", () => {
    expect(extractJson('{"a":1')).toBeNull();
  });
});
