// Device I/O over the device's own HTTP API.
//
// Plain `fetch` on purpose: the runner provides it, and staying free of the
// client library keeps the script small. The launcher's "Loading" screen lasts
// until the script has been parsed and linked, and library code — the layout
// engine plus the inlined font maps — dominated that.

/** Device address, set at build time with `busy-cli build --addr`. */
const addr = __BUSY_ADDR__;
const API = `${/^https?:\/\//i.test(addr) ? addr : `http://${addr}`}/api`;

/** A text element as /api/display/draw takes it. */
export interface TextElement {
  type: "text";
  id: string;
  text: string;
  font: string;
  color?: string;
  x?: number;
  y?: number;
  align?: string;
  display?: "front" | "back";
}

/** An image element as /api/display/draw takes it. */
export interface ImageElement {
  type: "image";
  id: string;
  path?: string;
  stock_path?: string;
  opacity?: number;
  x?: number;
  y?: number;
  align?: string;
  display?: "front" | "back";
}

export type DisplayElement = TextElement | ImageElement;

export interface DrawRequest {
  application_name: string;
  priority: number;
  led_notification_color?: string;
  elements: DisplayElement[];
}

/** The stored settings document: a version plus a flat field id → value map. */
export interface AppSettingsDocument {
  version: number;
  values: Record<string, unknown>;
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`${API}${path}`, init);
  if (!response.ok) {
    throw new Error(`${path}: HTTP ${response.status} ${await response.text()}`);
  }
  return response;
}

function post(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export async function displayDraw(request: DrawRequest): Promise<void> {
  await call("/display/draw", post(request));
}

/** Plays a file from the app's own assets, e.g. "sounds/countdown_tick.snd". */
export async function audioPlay(applicationName: string, file: string): Promise<void> {
  await call("/audio/play", post({ application_name: applicationName, path: file }));
}

export async function getAppSettings(appId: string): Promise<AppSettingsDocument> {
  const response = await call(`/apps/settings?app_id=${encodeURIComponent(appId)}`);
  return (await response.json()) as AppSettingsDocument;
}

export async function setAppSettings(
  appId: string,
  settings: AppSettingsDocument,
): Promise<void> {
  await call(`/apps/settings?app_id=${encodeURIComponent(appId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}
