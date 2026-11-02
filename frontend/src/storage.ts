import type { Language, Snapshot } from "./types";
import { isLanguage, LANGUAGE_IDS } from "./languages";

const DRAFT_PREFIX = "ai-tutor:draft:v1:";
export const bufferKey = (problemId: number, language: Language = "python") => `${problemId}:${language}`;
// Keep original Python keys in place: old drafts remain readable without migration writes.
export const draftKey = (problemId: number, language: Language = "python") => language === "python"
  ? `${DRAFT_PREFIX}${problemId}`
  : `ai-tutor:draft:v2:${bufferKey(problemId, language)}`;
export function restoreCode(
  problemId: number,
  template: string,
  storage: Storage,
  language: Language = "python",
): string {
  return storage.getItem(draftKey(problemId, language)) ?? template;
}
export function saveCode(
  problemId: number,
  code: string,
  storage: Storage,
  language: Language = "python",
): void {
  storage.setItem(draftKey(problemId, language), code);
}
export function exportDrafts(
  problemIds: number[],
  storage: Storage,
  overrides: Record<string, string> = {},
): string {
  const drafts: Record<string, Partial<Record<Language, string>>> = {};
  problemIds.forEach((id) => {
    LANGUAGE_IDS.forEach((language) => {
      const key = bufferKey(id, language);
      const overrideKey = Object.prototype.hasOwnProperty.call(overrides, key)
        ? key : language === "python" && Object.prototype.hasOwnProperty.call(overrides, String(id)) ? String(id) : null;
      // A quota failure may leave older stored code behind. Even an empty
      // unsaved buffer takes priority over its persisted version.
      const code = overrideKey !== null ? overrides[overrideKey] : storage.getItem(draftKey(id, language));
      if (code !== null) (drafts[id] ??= {})[language] = code;
    });
  });
  return JSON.stringify(
    { schema_version: 2, drafts, exported_at: new Date().toISOString() },
    null,
    2,
  );
}
export function importDrafts(
  text: string,
  problemIds: number[],
  storage: Storage,
  overrides: Record<string, string> = {},
) {
  const data: unknown = JSON.parse(text);
  if (
    !data ||
    typeof data !== "object" ||
    !("drafts" in data) ||
    !("schema_version" in data) ||
    ![1, 2].includes(Number(data.schema_version)) || typeof data.schema_version !== "number"
  ) {
    throw new Error("草稿文件格式不正确，请导入本项目导出的 JSON。");
  }
  const drafts = data.drafts;
  if (
    !drafts ||
    typeof drafts !== "object" ||
    Array.isArray(drafts) ||
    Object.entries(drafts).some(([id]) => !/^[1-9]\d*$/.test(id))
  ) {
    throw new Error("草稿内容不正确：题号和代码需要使用字符串。");
  }
  const entries: Array<[number, Language, string]> = [];
  for (const [id, value] of Object.entries(drafts)) {
    const languages: unknown = data.schema_version === 1 ? { python: value } : value;
    if (!languages || typeof languages !== "object" || Array.isArray(languages))
      throw new Error("草稿内容不正确：每道题需要包含语言和代码。");
    for (const [language, code] of Object.entries(languages)) {
      if (!isLanguage(language) || typeof code !== "string")
        throw new Error("草稿内容不正确：只支持 Python 3、Java、C、C++ 的字符串代码。");
      entries.push([Number(id), language, code]);
    }
  }
  let imported = 0,
    conflicts = 0,
    ignored = 0;
  for (const [id, language, code] of entries) {
    if (!problemIds.includes(id)) {
      ignored++;
      continue;
    }
    if (Object.prototype.hasOwnProperty.call(overrides, bufferKey(id, language))
      || (language === "python" && Object.prototype.hasOwnProperty.call(overrides, String(id)))
      || storage.getItem(draftKey(id, language)) !== null) {
      conflicts++;
      continue;
    }
    saveCode(id, code, storage, language);
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
    (first.language ?? "python") === (second.language ?? "python") &&
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
