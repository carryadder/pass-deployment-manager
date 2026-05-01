import { OpenAPI } from "./OpenAPI";

type Method = "GET" | "POST" | "PUT" | "DELETE";

export async function request<T>({
  method,
  url,
  body,
}: {
  method: Method;
  url: string;
  body?: unknown;
}): Promise<T> {
  const headers = new Headers();
  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (OpenAPI.TOKEN) {
    headers.set("Authorization", `Bearer ${OpenAPI.TOKEN}`);
  }

  const response = await fetch(`${OpenAPI.BASE}${url}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      // keep status text
    }
    throw new Error(detail || "Request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
