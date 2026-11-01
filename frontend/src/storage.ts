import type { Snapshot } from "./types";

const DRAFT_PREFIX = "ai-tutor:draft:v1:";
export const draftKey = (problemId: number) => `${DRAFT_PREFIX}${problemId}`;
export function restoreCode(
  problemId: number,
  template: string,
  storage: Storage,
): string {
  return storage.getItem(draftKey(problemId)) ?? template;
}
export function saveCode(
  problemId: number,
  code: string,
  storage: Storage,
): void {
  storage.setItem(draftKey(problemId), code);
}
export function exportDrafts(
  problemIds: number[],
  storage: Storage,
  overrides: Record<string, string> = {},
): string {
  const drafts: Record<string, string> = {};
  problemIds.forEach((id) => {
    // A quota failure may leave an older persisted draft behind. The caller
    // provides only unsaved buffers; an empty buffer is also an intentional edit.
    const code = Object.prototype.hasOwnProperty.call(overrides, String(id))
      ? overrides[id]
      : storage.getItem(draftKey(id));
    if (code !== null) drafts[id] = code;
  });
  return JSON.stringify(
    { schema_version: 1, drafts, exported_at: new Date().toISOString() },
    null,
    2,
  );
}
export function importDrafts(
  text: string,
  problemIds: number[],
  storage: Storage,
) {
  const data: unknown = JSON.parse(text);
  if (
    !data ||
    typeof data !== "object" ||
    !("drafts" in data) ||
    !("schema_version" in data) ||
    data.schema_version !== 1
  ) {
    throw new Error("草稿文件格式不正确，请导入本项目导出的 JSON。");
  }
  const drafts = data.drafts;
  if (
    !drafts ||
    typeof drafts !== "object" ||
    Array.isArray(drafts) ||
    Object.entries(drafts).some(
      ([id, code]) => !/^\d+$/.test(id) || typeof code !== "string",
    )
  ) {
    throw new Error("草稿内容不正确：题号和代码需要使用字符串。");
  }
  let imported = 0,
    conflicts = 0,
    ignored = 0;
  for (const [id, code] of Object.entries(drafts)) {
    if (!problemIds.includes(Number(id))) {
      ignored++;
      continue;
    }
    if (storage.getItem(draftKey(Number(id))) !== null) {
      conflicts++;
      continue;
    }
    saveCode(Number(id), code as string, storage);
    imported++;
  }
  return { imported, conflicts, ignored };
}
export function sameSnapshot(
  first: Snapshot,
  second: Snapshot | null,
): boolean {
  return (
    second !== null &&
    first.workspace_id === second.workspace_id &&
    first.problem_id === second.problem_id &&
    first.revision === second.revision &&
    first.code === second.code
  );
}
export function readPreference<T>(name: string, fallback: T): T {
  try {
    const value = localStorage.getItem(`ai-tutor:preferences:${name}`);
    return value ? (JSON.parse(value) as T) : fallback;
  } catch {
    return fallback;
  }
}
export function storePreference(name: string, value: unknown): void {
  try {
    localStorage.setItem(`ai-tutor:preferences:${name}`, JSON.stringify(value));
  } catch {
    /* Draft storage reports failures separately. */
  }
}
export function tabIdentity(): { workspace_id: string; revision: number } {
  try {
    const workspace_id =
      sessionStorage.getItem("ai-tutor:workspace") || crypto.randomUUID();
    sessionStorage.setItem("ai-tutor:workspace", workspace_id);
    return {
      workspace_id,
      revision: Number(sessionStorage.getItem("ai-tutor:revision") || 0) || 0,
    };
  } catch {
    return { workspace_id: crypto.randomUUID(), revision: 0 };
  }
}
export function rememberRevision(revision: number): void {
  try {
    sessionStorage.setItem("ai-tutor:revision", String(revision));
  } catch {
    /* The running tab still uses a stable in-memory identity. */
  }
}
