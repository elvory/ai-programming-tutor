import type { Language, Problem } from "./types";

export const LANGUAGES: Record<Language, { label: string; extension: string; mark: string }> = {
  python: { label: "Python 3", extension: "py", mark: "Py" },
  java: { label: "Java", extension: "java", mark: "J" },
  c: { label: "C", extension: "c", mark: "C" },
  cpp: { label: "C++", extension: "cpp", mark: "C++" },
};
export const LANGUAGE_IDS = Object.keys(LANGUAGES) as Language[];
export function isLanguage(value: unknown): value is Language {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(LANGUAGES, value);
}
export function problemTemplate(problem: Problem, language: Language): string {
  return problem.templates?.[language] ?? (language === "python"
    ? problem.python_template
    : `// 当前题目暂未提供 ${LANGUAGES[language].label} 模板，请参照官方函数签名。\n`);
}
