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
  it("restores an intentionally empty draft instead of replacing it with a template", () => {
    saveCode(1, "", localStorage);
    expect(restoreCode(1, "template", localStorage)).toBe("");
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
      "1": "newer draft",
      "20": "",
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
      "1": "newer unsaved draft B",
      "20": "other saved draft",
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
      JSON.parse(exportDrafts([1], unreadable, { "1": "" })).drafts,
    ).toEqual({ "1": "" });
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
    expect(
      sameSnapshot(original, { ...original, workspace_id: "tab-two" }),
    ).toBe(false);
  });
});
