import { beforeEach, describe, expect, it } from "vitest";
import {
  draftKey,
  exportDrafts,
  importDrafts,
  restoreCode,
  saveCode,
  sameSnapshot,
} from "./storage";

describe("persistent problem drafts", () => {
  beforeEach(() => localStorage.clear());
  it("isolates all four language drafts and preserves an untouched legacy Python key", () => {
    localStorage.setItem("ai-tutor:draft:v1:1", "legacy Python");
    saveCode(1, "Java source", localStorage, "java");
    saveCode(1, "C source", localStorage, "c");
    saveCode(1, "", localStorage, "cpp");
    expect(restoreCode(1, "python template", localStorage, "python")).toBe("legacy Python");
    expect(restoreCode(1, "java template", localStorage, "java")).toBe("Java source");
    expect(restoreCode(1, "c template", localStorage, "c")).toBe("C source");
    expect(restoreCode(1, "cpp template", localStorage, "cpp")).toBe("");
    expect(restoreCode(20, "other java template", localStorage, "java")).toBe("other java template");
    expect(localStorage.getItem("ai-tutor:draft:v1:1")).toBe("legacy Python");
  });
  it("restores an intentionally empty draft instead of replacing it with a template", () => {
    saveCode(1, "", localStorage);
    expect(restoreCode(1, "template", localStorage)).toBe("");
  });
  it("exports and imports four languages without replacing dirty buffers or existing drafts", () => {
    saveCode(1, "Python saved", localStorage);
    saveCode(1, "Java old", localStorage, "java");
    saveCode(20, "C saved", localStorage, "c");
    const exported = JSON.parse(exportDrafts([1, 20], localStorage, { "1:java": "Java unsaved", "1:cpp": "" }));
    expect(exported.schema_version).toBe(2);
    expect(exported.drafts).toEqual({ "1": { python: "Python saved", java: "Java unsaved", cpp: "" }, "20": { c: "C saved" } });
    localStorage.clear();
    saveCode(1, "keep Java", localStorage, "java");
    const result = importDrafts(JSON.stringify(exported), [1, 20], localStorage, { "20:c": "dirty C" });
    expect(result).toEqual({ imported: 2, conflicts: 2, ignored: 0 });
    expect(restoreCode(1, "", localStorage)).toBe("Python saved");
    expect(restoreCode(1, "", localStorage, "java")).toBe("keep Java");
    expect(restoreCode(1, "template", localStorage, "cpp")).toBe("");
    expect(localStorage.getItem(draftKey(20, "c"))).toBeNull();
  });
  it("restores independent drafts after navigation and a fresh read", () => {
    saveCode(1, "first draft", localStorage);
    saveCode(20, "second draft", localStorage);
    expect(restoreCode(1, "template", localStorage)).toBe("first draft");
    expect(restoreCode(20, "template", localStorage)).toBe("second draft");
    expect(restoreCode(198, "untouched template", localStorage)).toBe(
      "untouched template",
    );
    expect(localStorage.getItem(draftKey(198))).toBeNull();
  });
  it("imports older exported session drafts without overwriting newer local work", () => {
    saveCode(1, "newer draft", localStorage);
    const result = importDrafts(
      JSON.stringify({
        schema_version: 1,
        drafts: { "1": "old code", "20": "" },
      }),
      [1, 20],
      localStorage,
    );
    expect(result).toEqual({ imported: 1, conflicts: 1, ignored: 0 });
    expect(restoreCode(1, "template", localStorage)).toBe("newer draft");
    expect(restoreCode(20, "template", localStorage)).toBe("");
    expect(JSON.parse(exportDrafts([1, 20], localStorage)).drafts).toEqual({
      "1": { python: "newer draft" },
      "20": { python: "" },
    });
  });
  it("rejects malformed imports before changing any stored draft", () => {
    expect(() =>
      importDrafts('{"drafts":{"1":123}}', [1], localStorage),
    ).toThrow();
    expect(localStorage.length).toBe(0);
  });
  it("exports the latest unsaved override instead of an older persisted draft", () => {
    saveCode(1, "persisted draft A", localStorage);
    saveCode(20, "other saved draft", localStorage);
    const exported = JSON.parse(
      exportDrafts([1, 20], localStorage, { "1": "newer unsaved draft B" }),
    );
    expect(exported.drafts).toEqual({
      "1": { python: "newer unsaved draft B" },
      "20": { python: "other saved draft" },
    });
    expect(restoreCode(1, "template", localStorage)).toBe("persisted draft A");
  });
  it("exports an intentionally empty unsaved override and reports unreadable remaining storage", () => {
    const unreadable = {
      getItem: () => {
        throw new Error("storage unreadable");
      },
    } as unknown as Storage;
    expect(
      JSON.parse(exportDrafts([1], unreadable, { "1": "", "1:java": "J", "1:c": "C", "1:cpp": "CPP" })).drafts,
    ).toEqual({ "1": { python: "", java: "J", c: "C", cpp: "CPP" } });
    expect(() => exportDrafts([1, 20], unreadable, { "1": "latest" })).toThrow(
      "storage unreadable",
    );
  });
});

describe("async diagnosis isolation", () => {
  it("does not revive a result after editing back to the same code or switching problems", () => {
    const original = {
      workspace_id: "tab-one",
      problem_id: 1,
      code: "pass",
      revision: 1,
    };
    expect(sameSnapshot(original, { ...original })).toBe(true);
    expect(sameSnapshot(original, { ...original, revision: 3 })).toBe(false);
    expect(sameSnapshot(original, { ...original, problem_id: 20 })).toBe(false);
    expect(sameSnapshot(original, { ...original, language: "java" })).toBe(false);
    expect(
      sameSnapshot(original, { ...original, workspace_id: "tab-two" }),
    ).toBe(false);
  });
  it("rejects invalid languages and malformed later entries before writing an earlier valid draft", () => {
    localStorage.clear();
    expect(() => importDrafts(JSON.stringify({ schema_version: 2, drafts: { "1": { java: "valid" }, "20": { javascript: "invalid" } } }), [1, 20], localStorage)).toThrow();
    expect(localStorage.length).toBe(0);
  });
});
