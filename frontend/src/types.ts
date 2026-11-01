export interface Problem {
  id: number;
  title_zh: string;
  title_en: string;
  slug: string;
  difficulty: "Easy" | "Medium" | "Hard";
  tags: string[];
  stage: number;
  summary: string;
  examples: { input: string; output: string; explanation?: string }[];
  constraints: string[];
  python_template: string;
  official_url: string;
  source_note: string;
}
export interface RouteStage {
  id: number;
  title: string;
  problems: Problem[];
}
export interface Bootstrap {
  problems: Problem[];
  route: RouteStage[];
  summary: {
    total_submissions: number;
    completed_problems: number;
    streak_days: number;
    recommended_stage: number;
    completed_ids: number[];
    counts_by_day: Record<string, number>;
  };
  heatmap: { date: string; count: number; level: number }[];
}
export type DisplayRow = Record<string, string>;
export interface History {
  records: DisplayRow[];
  activities: DisplayRow[];
}
export interface Snapshot {
  workspace_id: string;
  problem_id: number;
  code: string;
  revision: number;
}
export interface Diagnosis {
  error_type: string;
  knowledge: string;
  analysis: string;
  hints: string[];
  source: string;
  is_mock: boolean;
  model?: string;
}
export interface DiagnosisResult {
  diagnosis: Diagnosis;
  diagnosis_id: string;
  record_id: string | null;
  hint_level: number;
  hint_count: number;
  warning: string | null;
}

export type Page = "workbench" | "route" | "history";
export type MobilePanel = "problem" | "code" | "assistant";
