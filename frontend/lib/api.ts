/**
 * Fetch wrapper for the two endpoints the UI needs (spec §13.4).
 *
 * `GET /api/v1/features` is the single source of truth for which features exist — the
 * tier picker builds itself from it and never hardcodes a feature list.
 */

import type {
  AnalyzeRequest,
  AnalyzeResponse,
  FeatureCatalogEntry,
  FeatureCatalogResponse,
} from "./types";

/**
 * The backend's CORS default is `http://localhost:3000` for this origin; point
 * `NEXT_PUBLIC_API_BASE_URL` elsewhere (and set `TEXTROPY_CORS_ORIGINS` to match) when
 * the API is not on localhost:8000.
 */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** FastAPI puts the human-readable message in `detail`, which may itself be a list. */
async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        const messages = detail
          .map((item) =>
            item && typeof item === "object" && "msg" in item
              ? String((item as { msg: unknown }).msg)
              : null,
          )
          .filter((msg): msg is string => Boolean(msg));
        if (messages.length > 0) return messages.join("; ");
      }
      return JSON.stringify(detail);
    }
  } catch {
    // Non-JSON body (a proxy error page, say) — fall through to the status text.
  }
  return response.statusText || `Request failed with status ${response.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    // Network-level failure: the API is down, unreachable, or CORS rejected the call.
    throw new ApiError(
      `Could not reach the Textropy API at ${API_BASE_URL}. Is the backend running?`,
      null,
    );
  }

  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }

  return (await response.json()) as T;
}

export async function fetchFeatureCatalog(
  signal?: AbortSignal,
): Promise<FeatureCatalogEntry[]> {
  const body = await request<FeatureCatalogResponse>("/features", {
    method: "GET",
    signal,
  });
  return body.features;
}

export async function analyze(
  payload: AnalyzeRequest,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}
