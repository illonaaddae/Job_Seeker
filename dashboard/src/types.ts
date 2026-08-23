export type JobStatus =
  | "new"
  | "scored"
  | "shortlisted"
  | "drafted"
  | "applied"
  | "rejected_by_me"
  | "expired";

export type ApplicationStatus =
  | "draft"
  | "approved"
  | "sent"
  | "failed"
  | "replied"
  | "interview"
  | "offer"
  | "rejected"
  | "ghosted"
  | "withdrawn";

export interface ScoreBreakdown {
  score?: number;
  signals?: Record<string, number>;
  reasons?: string[];
  blockers?: string[];
  matched_skills?: string[];
  missing_skills?: string[];
  required_years?: number | null;
}

export interface Application {
  id: number;
  job_id: number;
  company_id: number | null;
  contact_id: number | null;
  channel: "email" | "portal" | "referral";
  status: ApplicationStatus;
  recipient_email: string;
  subject: string;
  body: string;
  cover_letter_path: string;
  cv_path: string;
  tailored_summary: string;
  generator: string;
  sent_at: string;
  notes: string;
  created_at: string;
  updated_at: string;
  job?: Job | null;
}

export interface Job {
  id: number;
  title: string;
  company_name: string;
  source: string;
  external_id: string;
  url: string;
  location: string;
  remote: number;
  employment_type: string;
  department: string;
  description: string;
  salary: string;
  posted_at: string;
  company_id: number | null;
  score: number;
  score_breakdown: ScoreBreakdown;
  status: JobStatus;
  discovered_at: string;
  application?: Application | null;
}

export interface Contact {
  id: number;
  company_id: number;
  email: string;
  name: string;
  title: string;
  linkedin: string;
  source: string;
  confidence: number;
  verified: number;
}

export interface Stats {
  jobs_total: number;
  companies_total: number;
  contacts_total: number;
  jobs_by_status: Record<string, number>;
  applications_by_status: Record<string, number>;
  sent: number;
  replied: number;
  positive: number;
  reply_rate: number;
  interview_rate: number;
  avg_score: number;
  followups_pending: number;
  sends_by_day: { day: string; n: number }[];
  send_enabled: boolean;
  writer: string;
  daily_cap: number;
  sent_today: number;
  next_followup: string | null;
}

export interface ActivityEvent {
  id: number;
  type: string;
  message: string;
  job_id: number | null;
  application_id: number | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Reply {
  id: number;
  application_id: number | null;
  from_addr: string;
  subject: string;
  snippet: string;
  classification: string;
  received_at: string;
}

export interface PendingFollowup {
  id: number;
  application_id: number;
  job_id: number;
  sequence_no: number;
  due_at: string;
  recipient_email: string;
  title: string;
  company_name: string;
}

export interface ReadinessCheck {
  key: string;
  label: string;
  ready: boolean;
  unlocks: string;
  how: string;
}

export interface Profile {
  identity: Record<string, string>;
  readiness?: ReadinessCheck[];
  targeting: Record<string, unknown>;
  skills: { core: string[]; secondary: string[] };
  settings: {
    daily_cap: number;
    min_score_to_draft: number;
    min_score_to_send: number;
    send_enabled: boolean;
    writer: string;
  };
}

export interface ApplyField {
  label: string;
  value: string;
  group: "you" | "links" | "logistics" | "writing";
}

export interface ApplyDocument {
  label: string;
  filename: string;
  url: string;
}

export interface FormAnswer {
  key: string;
  question: string;
  asked_as: string[];
  answer: string;
  words: number;
  source: "yours" | "tailored";
}

export interface ApplyPack {
  job: Job;
  application: Application | null;
  fields: ApplyField[];
  documents: ApplyDocument[];
  answers: FormAnswer[];
}

export interface SessionState {
  authenticated: boolean;
  auth_required: boolean;
  password_set: boolean;
}

export interface TaskStatus {
  stage: string | null;
  status: "idle" | "running" | "finished" | "failed";
  started_at?: string;
  finished_at?: string;
  result?: StageResult | null;
  error?: string;
}

export interface StageResult {
  stage: string;
  counts: Record<string, number>;
  messages: string[];
  items: Record<string, unknown>[];
}
