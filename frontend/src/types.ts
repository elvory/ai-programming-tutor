export type Language = "python" | "java" | "c" | "cpp";
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
  templates?: Partial<Record<Language, string>>;
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
    completed_by_language?: Record<Language, number[]>;
  };
  heatmap: { date: string; count: number; level: number }[];
  capability?: CapabilityProfileData;
}
export type SampleStatus = "empty" | "insufficient" | "available";
export interface CapabilityDimension {
  id: string;
  label: string;
  stages: number[];
  problem_ids: number[];
  total: number;
  completed_ids: number[];
  completed: number;
  percentage: number;
  sample_status: SampleStatus;
  recommended_problem_id: number | null;
}
export interface CapabilityProfileData {
  dimensions: CapabilityDimension[];
  completed_unique: number;
  total: number;
  sample_status: SampleStatus;
  strongest: string[];
  needs_attention: string[];
  recommendation: string;
  recommended_problem_id: number | null;
  unclassified_problem_ids: number[];
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
  language?: Language;
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
  language?: Language;
}

export type Page = "workbench" | "route" | "history";
export type MobilePanel = "problem" | "code" | "assistant";
