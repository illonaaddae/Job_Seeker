import type {
  ActivityEvent,
  Application,
  Contact,
  Job,
  PendingFollowup,
  Profile,
  Reply,
  SessionState,
  ApplyPack,
  Stats,
  TaskStatus,
} from "./types";

const TOKEN_KEY = "jobseeker.token";

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(value: string): void {
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private browsing, nothing to do */
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  if (response.status === 401) {
    // The session expired or was never established. The server renders the
    // login screen for any page request, so a reload is the whole flow.
    window.location.reload();
    throw new ApiError("sign in required", 401);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { error?: string };
      if (payload.error) detail = payload.error;
    } catch {
      /* the body was not JSON, keep the status text */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

function post<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export interface JobQuery {
  status?: string;
  min_score?: number;
  source?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  session: () => request<SessionState>("/auth/session"),
  applyPack: (jobId: number) => request<ApplyPack>(`/api/jobs/${jobId}/apply-pack`),
  rebuildAnswers: (jobId: number) =>
    post<{ answers: ApplyPack["answers"] }>(`/api/jobs/${jobId}/answers`, {}),

  changePassword: (currentPassword: string, newPassword: string) =>
    post<{ ok: boolean }>("/auth/password", {
      current_password: currentPassword,
      new_password: newPassword,
    }),

  signOut: async () => {
    await fetch("/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    window.location.reload();
  },

  profile: () => request<Profile>("/api/profile"),

  jobs: (query: JobQuery = {}) => {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== "" && value !== null) {
        params.set(key, String(value));
      }
    });
    const suffix = params.toString();
    return request<{ jobs: Job[] }>(`/api/jobs${suffix ? `?${suffix}` : ""}`);
  },

  job: (id: number) =>
    request<{
      job: Job;
      application: Application | null;
      company: Record<string, unknown> | null;
      contacts: Contact[];
    }>(`/api/jobs/${id}`),

  applications: (status?: string) =>
    request<{ applications: Application[]; counts: Record<string, number> }>(
      `/api/applications${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),

  events: (limit = 30) => request<{ events: ActivityEvent[] }>(`/api/events?limit=${limit}`),
  replies: () => request<{ replies: Reply[] }>("/api/replies"),
  followups: () => request<{ followups: PendingFollowup[] }>("/api/followups"),

  draftJob: (id: number, writer?: string) =>
    post<{ application: Application }>(`/api/jobs/${id}/draft`, { writer }),
  setJobStatus: (id: number, status: string) => post(`/api/jobs/${id}/status`, { status }),
  approve: (applicationId: number) => post(`/api/applications/${applicationId}/approve`),
  setApplicationStatus: (applicationId: number, status: string) =>
    post(`/api/applications/${applicationId}/status`, { status }),
  importUrl: (url: string) => post<{ job: Job }>("/api/jobs/import", { url }),

  // Starting a stage returns as soon as the work begins. A discover run takes
  // minutes and hosts cut long requests off, so the outcome is polled.
  run: (stage: string, body: Record<string, unknown> = {}) =>
    post<{ stage: string; status: string }>(`/api/run/${stage}`, body),

  runStatus: () => request<TaskStatus>("/api/run/status"),
};
