import type {
  Shoe,
  ShoeMileage,
  RetireShoeRequest,
  RetiredShoeInfo,
  DayMileage,
  RawDayMileage,
  RawDayTrainingLoad,
  DayTrainingLoad,
  RawDayTrimp,
  DayTrimp,
  RunSortBy,
  SortOrder,
  SyncResponse,
  RawRunDetail,
  RunDetail,
  StravaAuthStatus,
  GoogleAuthStatus,
} from "./types";
import { useDashboardStore } from "@/store";
import { ensureValidToken } from "@/lib/oauth/refresh";

/**
 * Get authorization headers for authenticated API requests.
 * Ensures token is valid (refreshing if needed) and returns headers with Bearer token.
 * Throws if authentication is required but no valid token is available.
 */
async function getAuthHeaders(): Promise<HeadersInit> {
  const tokenValid = await ensureValidToken();
  if (!tokenValid) {
    throw new Error("Authentication required. Please log in again.");
  }

  const { accessToken } = useDashboardStore.getState();
  const headers: HeadersInit = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  return headers;
}

// Fetch functions
//
// To pull data from the API

export async function fetchShoeMileage(
  includeRetired: boolean = false,
): Promise<ShoeMileage[]> {
  const headers = await getAuthHeaders();
  const url = new URL(
    `${import.meta.env.VITE_API_URL}/metrics/mileage/by-shoe`,
  );
  if (includeRetired) {
    url.searchParams.set("include_retired", "true");
  }
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error("Failed to fetch shoe mileage");
  return res.json() as Promise<ShoeMileage[]>;
}

export interface FetchDayMileageParams {
  startDate?: Date;
  endDate?: Date;
  userTimezone?: string;
}

export async function fetchDayMileage({
  startDate,
  endDate,
  userTimezone,
}: FetchDayMileageParams = {}): Promise<DayMileage[]> {
  const headers = await getAuthHeaders();
  const url = new URL(`${import.meta.env.VITE_API_URL}/metrics/mileage/by-day`);
  if (startDate) {
    url.searchParams.set("start", toDateString(startDate));
  }
  if (endDate) {
    url.searchParams.set("end", toDateString(endDate));
  }
  if (userTimezone) {
    url.searchParams.set("user_timezone", userTimezone);
  }
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error("Failed to fetch day mileage");
  const rawDayMileage = await (res.json() as Promise<RawDayMileage[]>);
  return rawDayMileage.map(dayMileageFromRawDayMileage);
}

export interface FetchRollingDayMileageParams {
  startDate?: Date;
  endDate?: Date;
  window?: number; // Number of days to look back for rolling average
  userTimezone?: string;
}

export async function fetchRollingDayMileage({
  startDate,
  endDate,
  window,
  userTimezone,
}: FetchRollingDayMileageParams = {}): Promise<DayMileage[]> {
  const headers = await getAuthHeaders();
  const url = new URL(
    `${import.meta.env.VITE_API_URL}/metrics/mileage/rolling-by-day`,
  );
  if (startDate) {
    url.searchParams.set("start", toDateString(startDate));
  }
  if (endDate) {
    url.searchParams.set("end", toDateString(endDate));
  }
  if (window) {
    url.searchParams.set("window", window.toString());
  }
  if (userTimezone) {
    url.searchParams.set("user_timezone", userTimezone);
  }
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error("Failed to fetch rolling day mileage");
  const rawDayMileage = await (res.json() as Promise<RawDayMileage[]>);
  return rawDayMileage.map(dayMileageFromRawDayMileage);
}

export interface FetchRunsParams {
  startDate?: Date;
  endDate?: Date;
  userTimezone?: string;
  sortBy?: RunSortBy;
  sortOrder?: SortOrder;
  // Extended for details endpoint
  synced?: "synced" | "unsynced" | "all";
}

// Unified run details
export async function fetchRunDetails({
  startDate,
  endDate,
  sortBy = "date",
  sortOrder = "desc",
  synced,
}: FetchRunsParams = {}): Promise<RunDetail[]> {
  const headers = await getAuthHeaders();
  // Use unambiguous path to avoid collision with dynamic /runs/{run_id}
  const url = new URL(`${import.meta.env.VITE_API_URL}/runs-details`);
  if (startDate) {
    url.searchParams.set("start", toDateString(startDate));
  }
  if (endDate) {
    url.searchParams.set("end", toDateString(endDate));
  }
  if (sortBy) {
    url.searchParams.set("sort_by", sortBy);
  }
  if (sortOrder) {
    url.searchParams.set("sort_order", sortOrder);
  }
  // Optional synced filter ("synced" | "unsynced" | "all") → boolean query
  if (synced === "synced") url.searchParams.set("synced", "true");
  else if (synced === "unsynced") url.searchParams.set("synced", "false");

  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error("Failed to fetch run details");

  const rawDetails = (await res.json()) as RawRunDetail[];
  return rawDetails.map(runDetailFromRawRunDetail);
}

export interface FetchRecentRunsParams {
  limit?: number;
  userTimezone?: string;
}

export interface fetchTotalMileageParams {
  startDate?: Date;
  endDate?: Date;
  userTimezone?: string;
}

export async function fetchTotalMileage({
  startDate,
  endDate,
  userTimezone,
}: fetchTotalMileageParams = {}): Promise<number> {
  const headers = await getAuthHeaders();
  const url = new URL(`${import.meta.env.VITE_API_URL}/metrics/mileage/total`);
  if (startDate) {
    url.searchParams.set("start", toDateString(startDate));
  }
  if (endDate) {
    url.searchParams.set("end", toDateString(endDate));
  }
  if (userTimezone) {
    url.searchParams.set("user_timezone", userTimezone);
  }
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error("Failed to fetch mileage");
  const totalMileage = (await res.json()) as number;
  return totalMileage;
}

export interface fetchTotalSecondsParams {
  startDate?: Date;
  endDate?: Date;
  userTimezone?: string;
}

export async function fetchTotalSeconds({
  startDate,
  endDate,
  userTimezone,
}: fetchTotalSecondsParams = {}): Promise<number> {
  const headers = await getAuthHeaders();
  const url = new URL(`${import.meta.env.VITE_API_URL}/metrics/seconds/total`);
  if (startDate) {
    url.searchParams.set("start", toDateString(startDate));
  }
  if (endDate) {
    url.searchParams.set("end", toDateString(endDate));
  }
  if (userTimezone) {
    url.searchParams.set("user_timezone", userTimezone);
  }
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error("Failed to fetch seconds");
  const totalSeconds = (await res.json()) as number;
  return totalSeconds;
}

export interface fetchDayTrainingLoadParams {
  startDate: Date;
  endDate: Date;
  maxHr: number;
  restingHr: number;
  sex: "M" | "F";
  userTimezone?: string;
}

export async function fetchDayTrainingLoad({
  startDate,
  endDate,
  maxHr,
  restingHr,
  sex,
  userTimezone,
}: fetchDayTrainingLoadParams): Promise<DayTrainingLoad[]> {
  const headers = await getAuthHeaders();
  const url = new URL(
    `${import.meta.env.VITE_API_URL}/metrics/training-load/by-day`,
  );
  url.searchParams.set("start", toDateString(startDate));
  url.searchParams.set("end", toDateString(endDate));
  url.searchParams.set("max_hr", maxHr.toString());
  url.searchParams.set("resting_hr", restingHr.toString());
  url.searchParams.set("sex", sex);
  if (userTimezone) {
    url.searchParams.set("user_timezone", userTimezone);
  }
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error("Failed to fetch training load");
  const rawDayTrainingLoad = await (res.json() as Promise<
    RawDayTrainingLoad[]
  >);
  return rawDayTrainingLoad.map(dayTrainingLoadFromRawDayTrainingLoad);
}

// Type conversions
//
// To convert received data into application types.

function toDateString(d: Date): string {
  return d.toISOString().split("T")[0]; // "YYYY-MM-DD"
}

// Removed legacy Run converter; UI consumes RunDetail exclusively

// Removed runs-with-shoes converter in favor of RunDetail flow

function runDetailFromRawRunDetail(raw: RawRunDetail): RunDetail {
  // Parse datetime first if available, then derive local date
  let datetime: Date | undefined;
  let date: Date | undefined;
  if (raw.datetime_utc) {
    const utcString = raw.datetime_utc.endsWith("Z")
      ? raw.datetime_utc
      : raw.datetime_utc + "Z";
    const parsed = new Date(utcString);
    if (!isNaN(parsed.getTime())) {
      datetime = parsed;
      date = new Date(
        parsed.getFullYear(),
        parsed.getMonth(),
        parsed.getDate(),
      );
    }
  }
  if (!date) {
    // Backend guarantees datetime_utc; but keep a fallback to today
    date = new Date();
  }

  return {
    id: raw.id,
    date,
    datetime,
    type: raw.type,
    distance: raw.distance,
    duration: raw.duration,
    source: raw.source,
    avg_heart_rate: raw.avg_heart_rate ?? null,
    shoe_id: raw.shoe_id ?? null,
    shoes: raw.shoes ?? null,
    shoe_retirement_notes: raw.shoe_retirement_notes ?? null,
    deleted_at: raw.deleted_at ? new Date(raw.deleted_at) : null,
    version: raw.version ?? null,
    is_synced: !!raw.is_synced,
    sync_status: raw.sync_status ?? null,
    synced_at: raw.synced_at ? new Date(raw.synced_at) : null,
    google_event_id: raw.google_event_id ?? null,
    synced_version: raw.synced_version ?? null,
    error_message: raw.error_message ?? null,
  };
}

function dayMileageFromRawDayMileage(rawDayMileage: RawDayMileage): DayMileage {
  if (typeof rawDayMileage !== "object" || rawDayMileage === null) {
    throw new Error("Invalid day mileage data");
  }
  // Convert the date string to a Date object
  const date = new Date(rawDayMileage.date);
  return {
    date,
    mileage: rawDayMileage.mileage,
  };
}

function dayTrainingLoadFromRawDayTrainingLoad(
  rawDayTrainingLoad: RawDayTrainingLoad,
): DayTrainingLoad {
  if (typeof rawDayTrainingLoad !== "object" || rawDayTrainingLoad === null) {
    throw new Error("Invalid training load data");
  }
  // Convert the date string to a Date object
  // Dates come in like "2025-06-30" and we need to convert them to Date objects, without worrying about timezones.
  const date = new Date(rawDayTrainingLoad.date + "T00:00:00");
  return {
    date,
    training_load: rawDayTrainingLoad.training_load,
  };
}

function dayTrimpFromRawDayTrimp(rawDayTrimp: RawDayTrimp): DayTrimp {
  return {
    date: new Date(rawDayTrimp.date + "T00:00:00"), // Ensure it's treated as local date
    trimp: rawDayTrimp.trimp,
  };
}

export async function fetchDayTrimp(
  start?: Date,
  end?: Date,
  userTimezone?: string,
): Promise<DayTrimp[]> {
  const headers = await getAuthHeaders();
  const url = new URL(`${import.meta.env.VITE_API_URL}/metrics/trimp/by-day`);
  if (start) {
    url.searchParams.set("start", toDateString(start));
  }
  if (end) {
    url.searchParams.set("end", toDateString(end));
  }
  if (userTimezone) {
    url.searchParams.set("user_timezone", userTimezone);
  }
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Failed to fetch day TRIMP: ${res.statusText}`);
  }
  const rawDayTrimps = await (res.json() as Promise<RawDayTrimp[]>);
  return rawDayTrimps.map(dayTrimpFromRawDayTrimp);
}

export interface RefreshDataResponse {
  status: string;
  message: string;
  total_external_runs: number;
  existing_in_db: number;
  new_runs_found: number;
  new_runs_inserted: number;
  new_run_ids: string[];
  updated_at: string;
}

export async function refreshData(): Promise<RefreshDataResponse> {
  // Ensure token is valid, refresh if needed
  const tokenValid = await ensureValidToken();
  if (!tokenValid) {
    throw new Error("Authentication required. Please log in again.");
  }

  // Get auth from store
  const auth = useDashboardStore.getState();
  const { accessToken } = auth;

  const headers: HeadersInit = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const url = new URL(`${import.meta.env.VITE_API_URL}/strava/update-data`);
  const res = await fetch(url, {
    method: "POST",
    headers,
  });

  if (res.status === 401) {
    throw new Error(
      "Authentication required. Please log in to refresh Strava data.",
    );
  }

  if (!res.ok) {
    throw new Error(`Failed to refresh Strava data: ${res.statusText}`);
  }

  return res.json() as Promise<RefreshDataResponse>;
}

export interface UploadMmfCsvResponse {
  inserted_count: number;
  total_runs_found: number;
  existing_runs: number;
  updated_at: string;
  message: string;
}

export async function uploadMmfCsv(
  file: File,
  timezone?: string,
): Promise<UploadMmfCsvResponse> {
  // Ensure token is valid, refresh if needed
  const tokenValid = await ensureValidToken();
  if (!tokenValid) {
    throw new Error("Authentication required. Please log in again.");
  }

  // Get auth from store
  const auth = useDashboardStore.getState();
  const { accessToken } = auth;

  const formData = new FormData();
  formData.append("file", file);
  if (timezone) {
    formData.append("timezone", timezone);
  }

  const headers: HeadersInit = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const url = new URL(`${import.meta.env.VITE_API_URL}/mmf/upload-csv`);
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
  });

  if (res.status === 401) {
    throw new Error(
      "Authentication required. Please log in to upload MMF data.",
    );
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Failed to upload MMF data: ${res.statusText}`,
    );
  }

  return res.json() as Promise<UploadMmfCsvResponse>;
}

// Shoe retirement management functions

export async function updateShoe(
  shoeId: string,
  request: RetireShoeRequest,
): Promise<{ message: string }> {
  // Ensure token is valid, refresh if needed
  const tokenValid = await ensureValidToken();
  if (!tokenValid) {
    throw new Error("Authentication required. Please log in again.");
  }

  // Get auth from store
  const auth = useDashboardStore.getState();
  const { accessToken } = auth;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const url = new URL(
    `${import.meta.env.VITE_API_URL}/shoes/${encodeURIComponent(shoeId)}`,
  );
  const res = await fetch(url, {
    method: "PATCH",
    headers,
    body: JSON.stringify(request),
  });

  if (res.status === 401) {
    throw new Error("Authentication required. Please log in to update shoes.");
  }

  if (!res.ok) {
    throw new Error(`Failed to update shoe: ${res.statusText}`);
  }

  return res.json() as Promise<{ message: string }>;
}

// Legacy function - retire shoe using new PATCH API
export async function retireShoe(
  shoeId: string,
  request: RetireShoeRequest,
): Promise<{ message: string }> {
  return updateShoe(shoeId, request);
}

// Legacy function - unretire shoe using new PATCH API
export async function unretireShoe(
  shoeId: string,
): Promise<{ message: string }> {
  return updateShoe(shoeId, { retired_at: null, retirement_notes: null });
}

export async function fetchShoes(retired?: boolean): Promise<Shoe[]> {
  const headers = await getAuthHeaders();
  const url = new URL(`${import.meta.env.VITE_API_URL}/shoes`);
  if (retired !== undefined) {
    url.searchParams.set("retired", retired.toString());
  }
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Failed to fetch shoes: ${res.statusText}`);
  }
  return res.json() as Promise<Shoe[]>;
}

// Legacy function - fetch retired shoes using new unified API
export async function fetchRetiredShoes(): Promise<RetiredShoeInfo[]> {
  const shoes = await fetchShoes(true);
  return shoes.map((shoe) => ({
    shoe,
    retired_at: shoe.retired_at!,
    retirement_notes: shoe.retirement_notes,
  }));
}

// Run editing functionality

export interface UpdateRunRequest {
  distance?: number;
  duration?: number;
  avg_heart_rate?: number | null;
  type?: "Outdoor Run" | "Treadmill Run";
  shoe_id?: string | null;
  datetime_utc?: string; // ISO datetime string
  change_reason?: string;
  changed_by: string;
}

export interface UpdateRunResponse {
  status: string;
  message: string;
  // The backend returns a raw run-like JSON object; we don't need a strict type here yet
  run: unknown;
  updated_fields: string[];
  updated_at: string;
  updated_by: string;
}

export async function updateRun(
  runId: string,
  request: UpdateRunRequest,
): Promise<UpdateRunResponse> {
  // Ensure token is valid, refresh if needed
  const tokenValid = await ensureValidToken();
  if (!tokenValid) {
    throw new Error("Authentication required. Please log in again.");
  }

  // Get auth from store
  const auth = useDashboardStore.getState();
  const { accessToken } = auth;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const url = new URL(
    `${import.meta.env.VITE_API_URL}/runs/${encodeURIComponent(runId)}`,
  );
  const res = await fetch(url, {
    method: "PATCH",
    headers,
    body: JSON.stringify(request),
  });

  if (res.status === 401) {
    throw new Error("Authentication required. Please log in to update runs.");
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Failed to update run: ${res.statusText}`,
    );
  }

  return res.json() as Promise<UpdateRunResponse>;
}

export interface EnvironmentResponse {
  environment: string;
}

export async function fetchEnvironment(): Promise<EnvironmentResponse> {
  const headers = await getAuthHeaders();
  const url = new URL(`${import.meta.env.VITE_API_URL}/environment`);
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Failed to fetch environment: ${res.statusText}`);
  }
  return res.json() as Promise<EnvironmentResponse>;
}

export async function fetchStravaAuthStatus(): Promise<StravaAuthStatus> {
  const headers = await getAuthHeaders();
  const url = new URL(`${import.meta.env.VITE_API_URL}/oauth/strava/status`);
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Failed to fetch Strava auth status: ${res.statusText}`);
  }
  return res.json() as Promise<StravaAuthStatus>;
}

export async function fetchGoogleAuthStatus(): Promise<GoogleAuthStatus> {
  const headers = await getAuthHeaders();
  const url = new URL(`${import.meta.env.VITE_API_URL}/oauth/google/status`);
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Failed to fetch Google auth status: ${res.statusText}`);
  }
  return res.json() as Promise<GoogleAuthStatus>;
}

export interface OAuthAuthorizeUrl {
  url: string;
}

export async function fetchStravaAuthorizeUrl(): Promise<OAuthAuthorizeUrl> {
  const headers = await getAuthHeaders();
  const url = new URL(
    `${import.meta.env.VITE_API_URL}/oauth/strava/authorize-url`,
  );
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Failed to fetch Strava authorize URL: ${res.statusText}`);
  }
  return res.json() as Promise<OAuthAuthorizeUrl>;
}

export async function fetchGoogleAuthorizeUrl(): Promise<OAuthAuthorizeUrl> {
  const headers = await getAuthHeaders();
  const url = new URL(
    `${import.meta.env.VITE_API_URL}/oauth/google/authorize-url`,
  );
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Failed to fetch Google authorize URL: ${res.statusText}`);
  }
  return res.json() as Promise<OAuthAuthorizeUrl>;
}

// Google Calendar sync API

export async function syncRun(runId: string): Promise<SyncResponse> {
  // Ensure token is valid, refresh if needed
  const tokenValid = await ensureValidToken();
  if (!tokenValid) {
    throw new Error("Authentication required. Please log in again.");
  }

  // Get auth from store
  const auth = useDashboardStore.getState();
  const { accessToken } = auth;

  const headers: HeadersInit = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const url = new URL(
    `${import.meta.env.VITE_API_URL}/sync/runs/${encodeURIComponent(runId)}`,
  );
  const res = await fetch(url, { method: "POST", headers });

  if (res.status === 401) {
    throw new Error(
      "Authentication required. Please log in to sync runs to calendar.",
    );
  }

  const data = (await res.json().catch(() => ({}))) as Partial<SyncResponse> &
    Record<string, unknown>;
  if (!res.ok || data.success === false) {
    const message =
      (typeof data.message === "string" && data.message) || res.statusText;
    throw new Error(`Failed to sync: ${message}`);
  }
  return data as SyncResponse;
}

export async function unsyncRun(runId: string): Promise<SyncResponse> {
  // Ensure token is valid, refresh if needed
  const tokenValid = await ensureValidToken();
  if (!tokenValid) {
    throw new Error("Authentication required. Please log in again.");
  }

  // Get auth from store
  const auth = useDashboardStore.getState();
  const { accessToken } = auth;

  const headers: HeadersInit = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const url = new URL(
    `${import.meta.env.VITE_API_URL}/sync/runs/${encodeURIComponent(runId)}`,
  );
  const res = await fetch(url, { method: "DELETE", headers });

  if (res.status === 401) {
    throw new Error(
      "Authentication required. Please log in to unsync runs from calendar.",
    );
  }

  const data = (await res.json().catch(() => ({}))) as Partial<SyncResponse> &
    Record<string, unknown>;
  if (!res.ok || data.success === false) {
    const message =
      (typeof data.message === "string" && data.message) || res.statusText;
    throw new Error(`Failed to unsync: ${message}`);
  }
  return data as SyncResponse;
}
