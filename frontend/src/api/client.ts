export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export interface AuthUser {
  id?: number | string;
  user_id?: string;
  username: string;
  email: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface ChatTask {
  task_id: string;
  session_id: string;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "WAITING_INPUT" | "CANCELED" | "RETRYING";
}

export interface TravelPlanItem {
  name?: string;
  price?: number | string;
  title?: string;
  description?: string;
  [key: string]: unknown;
}

export interface TravelPlanBudget {
  total?: number | string;
  [key: string]: unknown;
}

export interface TravelPlan {
  overview?: string;
  transport?: TravelPlanItem[];
  hotels?: TravelPlanItem[];
  itinerary?: TravelPlanItem[];
  budget?: TravelPlanBudget;
  notes?: string[];
  [key: string]: unknown;
}

export interface UserPreferences {
  budget: { max?: number } | null;
  transport_preferences: Record<string, unknown>;
  hotel_preferences: Record<string, unknown>;
  attraction_preferences: Record<string, unknown>;
  pace_preference: string | null;
  must_visit_places: string[];
  excluded_places: string[];
  notes: string[];
}

export interface BookingRecord {
  booking_id: string;
  user_id: string;
  session_id?: string | null;
  booking_type: string;
  item_name: string;
  amount?: number | null;
  currency: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BookingListResponse {
  bookings: BookingRecord[];
}

type ApiBody =
  | BodyInit
  | Record<string, unknown>
  | Array<unknown>
  | undefined;

type ApiFetchOptions = Omit<RequestInit, "body"> & {
  body?: ApiBody;
};

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
  token?: string
): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  const body = options.body;
  const hasBodyObject =
    body !== undefined &&
    typeof body === "object" &&
    !(body instanceof FormData) &&
    !(body instanceof Blob) &&
    !(body instanceof URLSearchParams) &&
    !(body instanceof ArrayBuffer);

  if (hasBodyObject && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    body: hasBodyObject
      ? JSON.stringify(body)
      : (options.body as BodyInit | null | undefined),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.message || data.code || "请求失败");
  }

  return data as T;
}

export async function createChatTask(message: string, token: string) {
  return apiFetch<ChatTask>(
    "/chat/async",
    {
      method: "POST",
      body: { message },
    },
    token
  );
}

export async function getTask(taskId: string, token: string) {
  return apiFetch<ChatTask>(`/task/${taskId}`, { method: "GET" }, token);
}

export async function getPlan(sessionId: string, token: string) {
  const raw = await apiFetch<Record<string, unknown>>(`/plan/${sessionId}`, { method: "GET" }, token);
  return {
    overview: raw.overview as string | undefined,
    transport: (raw.transport_plan ?? raw.transport) as TravelPlanItem[] | undefined,
    hotels: (raw.hotel_plan ?? raw.hotels) as TravelPlanItem[] | undefined,
    itinerary: (raw.itinerary_plan ?? raw.itinerary) as TravelPlanItem[] | undefined,
    budget: (raw.total_estimate ?? raw.budget) as TravelPlanBudget | undefined,
    notes: raw.notes as string[] | undefined,
    ...raw,
  } as TravelPlan;
}

export interface PlanHistoryResponse {
  session_id: string;
  history: TravelPlan[];
}

export interface HistorySession {
  session_id: string;
  created_at?: string;
  updated_at?: string;
  preview: string;
  title?: string;
  latest_plan?: TravelPlan;
}

export async function getPlanHistory(sessionId: string, token: string, limit: number = 5) {
  return apiFetch<PlanHistoryResponse>(
    `/plan/${sessionId}/history?limit=${limit}`,
    { method: "GET" },
    token
  );
}

export async function listSessions(token: string, limit: number = 20) {
  return apiFetch<{ sessions: HistorySession[] }>(
    `/sessions?limit=${limit}`,
    { method: "GET" },
    token
  );
}

export async function getUserPreferences(token: string) {
  return apiFetch<{ preferences: UserPreferences }>(
    "/preferences",
    { method: "GET" },
    token
  );
}

export async function updateUserPreferences(preferences: UserPreferences, token: string) {
  return apiFetch<{ preferences: UserPreferences }>(
    "/preferences",
    {
      method: "PUT",
      body: preferences as unknown as Record<string, unknown>,
    },
    token
  );
}

export interface CreateBookingRequest extends Record<string, unknown> {
  session_id?: string | null;
  booking_type: string;
  item_name: string;
  amount?: number | null;
  currency?: string;
  status?: string;
  payload?: Record<string, unknown>;
}

export async function createBookingRecord(request: CreateBookingRequest, token: string) {
  return apiFetch<BookingRecord>(
    "/bookings",
    {
      method: "POST",
      body: request,
    },
    token
  );
}

export async function listBookingRecords(
  token: string,
  limit: number = 20,
  sessionId?: string,
  bookingType?: string
) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (sessionId) {
    params.set("session_id", sessionId);
  }
  if (bookingType) {
    params.set("booking_type", bookingType);
  }
  return apiFetch<BookingListResponse>(
    `/bookings?${params.toString()}`,
    { method: "GET" },
    token
  );
}

export function getSessionHistoryKey(userId: number | string) {
  return `travel_session_history_${userId}`;
}

export function getAuthUserId(user: AuthUser): number | string {
  return user.user_id ?? user.id ?? user.username;
}

export function readSessionHistory(userId: number | string): HistorySession[] {
  const raw = localStorage.getItem(getSessionHistoryKey(userId));
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is HistorySession => {
      return Boolean(item && typeof item === "object" && typeof item.session_id === "string");
    });
  } catch {
    return [];
  }
}

export function rememberSession(userId: number | string, entry: HistorySession) {
  const now = new Date().toISOString();
  const normalized: HistorySession = {
    ...entry,
    created_at: entry.created_at ?? now,
    updated_at: now,
  };
  const previous = readSessionHistory(userId).filter(
    (item) => item.session_id !== normalized.session_id
  );
  localStorage.setItem(
    getSessionHistoryKey(userId),
    JSON.stringify([normalized, ...previous].slice(0, 20))
  );
}
