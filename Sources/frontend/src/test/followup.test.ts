import { describe, expect, it } from "vitest";

import { type ChatMessage, lastClarify } from "@/hooks/useChat";
import type { Trace } from "@/types/api";

const marker = { question: "How do I book counseling?", attribute: "campus", options: ["seoul", "erica"] };
const asked = { clarify: marker } as unknown as Trace;

describe("follow-up resolution marker", () => {
  it("sends back the last reply's clarify marker, per compare preset", () => {
    const chat: ChatMessage[] = [{ id: "1", role: "user", content: "How do I book counseling?" }, { id: "2", role: "assistant", content: "Which campus?", trace: asked }];
    expect(lastClarify(chat)).toEqual(marker);
    const compare: ChatMessage[] = [{ id: "2", role: "assistant", content: "", runs: [
      { presetId: "B0", name: "B0", content: "", status: "done", trace: {} as Trace },
      { presetId: "AP", name: "AP", content: "", status: "done", trace: asked }] }];
    expect(lastClarify(compare, "B0")).toBeNull();
    expect(lastClarify(compare, "AP")).toEqual(marker); // by preset id, so reordered columns keep their marker
    expect(lastClarify(compare, "R16")).toBeNull();
  });

  it("sends nothing after a normal answer", () => {
    expect(lastClarify([{ id: "2", role: "assistant", content: "Answer", trace: {} as Trace }])).toBeNull();
    expect(lastClarify([])).toBeNull();
  });
});
