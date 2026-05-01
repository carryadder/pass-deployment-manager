import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { Download, PauseCircle, PlayCircle, Radio, RefreshCw, Search } from "lucide-react";

import { OpenAPI } from "@/api/generated";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

type ConnectionState = "connecting" | "open" | "reconnecting" | "closed" | "error";

type LogLine = {
  id: number;
  raw: string;
  message: string;
  level: string | null;
};

const MAX_BUFFERED_LINES = 2000;

function normalizeLevel(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  return value.trim().toUpperCase();
}

function parseLogLine(raw: string): Pick<LogLine, "message" | "level"> {
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const level =
      normalizeLevel(parsed.level) ??
      normalizeLevel(parsed.lvl) ??
      normalizeLevel(parsed.severity) ??
      normalizeLevel(parsed.log_level);
    const message =
      typeof parsed.message === "string"
        ? parsed.message
        : typeof parsed.msg === "string"
          ? parsed.msg
          : typeof parsed.event === "string"
            ? parsed.event
            : raw;
    return { message, level };
  } catch {
    return { message: raw, level: null };
  }
}

function buildLogsSocketUrl(serviceId: string, tail: number, follow: boolean, token: string | null) {
  const base = OpenAPI.BASE
    ? new URL(OpenAPI.BASE, window.location.origin)
    : new URL(window.location.origin);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = `/api/services/${serviceId}/logs`;
  base.searchParams.set("tail", String(tail));
  base.searchParams.set("follow", follow ? "true" : "false");
  if (token) {
    base.searchParams.set("token", token);
  }
  return base.toString();
}

function connectionTone(state: ConnectionState) {
  if (state === "open") {
    return "text-moss";
  }
  if (state === "connecting" || state === "reconnecting") {
    return "text-slate";
  }
  if (state === "closed") {
    return "text-ink/55";
  }
  return "text-coral";
}

export function ServiceLogsTab({ serviceId }: { serviceId: string }) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const [lines, setLines] = useState<LogLine[]>([]);
  const [tailInput, setTailInput] = useState("200");
  const [downloadInput, setDownloadInput] = useState("200");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim().toLowerCase());
  const [follow, setFollow] = useState(true);
  const [paused, setPaused] = useState(false);
  const [levelFilter, setLevelFilter] = useState("all");
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [reconnectKey, setReconnectKey] = useState(0);
  const [appliedTail, setAppliedTail] = useState(200);
  const [manualPaused, setManualPaused] = useState(false);
  const nextIdRef = useRef(0);
  const logViewportRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setLines([]);
  }, [serviceId]);

  useEffect(() => {
    if (!serviceId) {
      return;
    }

    let isCancelled = false;
    let reconnectTimer: number | null = null;
    const socket = new WebSocket(buildLogsSocketUrl(serviceId, appliedTail, follow, accessToken));
    setConnectionState(reconnectKey === 0 ? "connecting" : "reconnecting");
    setConnectionError(null);

    socket.onopen = () => {
      if (isCancelled) {
        socket.close();
        return;
      }
      setConnectionState("open");
    };

    socket.onmessage = (event) => {
      const raw = String(event.data);
      const parsed = parseLogLine(raw);
      startTransition(() => {
        setLines((current) => {
          const next = [
            ...current,
            {
              id: nextIdRef.current++,
              raw,
              message: parsed.message,
              level: parsed.level,
            },
          ];
          return next.length > MAX_BUFFERED_LINES ? next.slice(next.length - MAX_BUFFERED_LINES) : next;
        });
      });
    };

    socket.onerror = () => {
      if (!isCancelled) {
        setConnectionState("error");
        setConnectionError("The log stream hit a websocket error.");
      }
    };

    socket.onclose = (event) => {
      if (isCancelled) {
        return;
      }
      if (!event.wasClean && follow) {
        setConnectionState("reconnecting");
        reconnectTimer = window.setTimeout(() => {
          setReconnectKey((current) => current + 1);
        }, 1500);
        return;
      }
      setConnectionState("closed");
      if (event.reason) {
        setConnectionError(event.reason);
      }
    };

    return () => {
      isCancelled = true;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      socket.close(1000, "cleanup");
    };
  }, [accessToken, appliedTail, follow, reconnectKey, serviceId]);

  useEffect(() => {
    if (paused || manualPaused) {
      return;
    }
    const viewport = logViewportRef.current;
    if (!viewport) {
      return;
    }
    viewport.scrollTop = viewport.scrollHeight;
  }, [lines, manualPaused, paused]);

  const levelOptions = useMemo(() => {
    return Array.from(
      new Set(
        lines
          .map((line) => line.level)
          .filter((line): line is string => Boolean(line)),
      ),
    ).sort();
  }, [lines]);

  const filteredLines = useMemo(() => {
    return lines.filter((line) => {
      if (levelFilter !== "all" && line.level !== levelFilter) {
        return false;
      }
      if (!deferredSearch) {
        return true;
      }
      return `${line.raw}\n${line.message}`.toLowerCase().includes(deferredSearch);
    });
  }, [deferredSearch, levelFilter, lines]);

  const visibleCount = filteredLines.length;
  const totalCount = lines.length;

  function downloadLogs() {
    const requested = Math.max(1, Number(downloadInput) || 200);
    const payload = filteredLines
      .slice(Math.max(filteredLines.length - requested, 0))
      .map((line) => line.raw)
      .join("\n");
    const blob = new Blob([payload], { type: "text/plain;charset=utf-8" });
    const objectUrl = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `service-${serviceId}-logs.log`;
    anchor.click();
    window.URL.revokeObjectURL(objectUrl);
  }

  return (
    <div className="grid gap-6">
      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Live logs</p>
            <h4 className="mt-2 text-2xl font-semibold">Streaming container output</h4>
            <p className="mt-2 max-w-2xl text-sm text-ink/65">
              Search, filter, pause scrolling, and export the recent log buffer without leaving the service detail page.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className={cn("inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium", connectionTone(connectionState))}>
              <Radio className="h-4 w-4" />
              {connectionState}
            </div>
            <Button
              variant="secondary"
              size="sm"
              className="gap-2"
              onClick={() => setReconnectKey((current) => current + 1)}
            >
              <RefreshCw className="h-4 w-4" />
              Reconnect
            </Button>
            <Button
              variant={manualPaused ? "primary" : "secondary"}
              size="sm"
              className="gap-2"
              onClick={() => setManualPaused((current) => !current)}
            >
              {manualPaused ? <PlayCircle className="h-4 w-4" /> : <PauseCircle className="h-4 w-4" />}
              {manualPaused ? "Resume scroll" : "Pause scroll"}
            </Button>
          </div>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-[1.2fr_0.8fr_0.8fr_0.8fr]">
          <label className="space-y-2 text-sm text-ink/70">
            <span>Search logs</span>
            <div className="relative">
              <Search className="pointer-events-none absolute left-4 top-4 h-4 w-4 text-ink/35" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search message text or JSON payload..."
                className="pl-10"
              />
            </div>
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>Backlog tail</span>
            <div className="flex gap-2">
              <Input value={tailInput} onChange={(event) => setTailInput(event.target.value)} inputMode="numeric" />
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setLines([]);
                  setAppliedTail(Math.max(0, Number(tailInput) || 200));
                  setReconnectKey((current) => current + 1);
                }}
              >
                Apply
              </Button>
            </div>
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>Level filter</span>
            <select
              value={levelFilter}
              onChange={(event) => setLevelFilter(event.target.value)}
              className="flex h-12 w-full rounded-2xl border border-ink/10 bg-white px-4 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-coral/40"
            >
              <option value="all">All levels</option>
              {levelOptions.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>Download last N</span>
            <div className="flex gap-2">
              <Input value={downloadInput} onChange={(event) => setDownloadInput(event.target.value)} inputMode="numeric" />
              <Button size="sm" variant="secondary" className="gap-2" onClick={downloadLogs}>
                <Download className="h-4 w-4" />
                Save
              </Button>
            </div>
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-ink/55">
          <p>
            Showing {visibleCount} of {totalCount} buffered lines
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className={cn(
                "rounded-full px-3 py-1 font-medium",
                follow ? "bg-ink text-mist" : "bg-ink/8 text-ink/70",
              )}
              onClick={() => setFollow((current) => !current)}
            >
              Follow: {follow ? "on" : "off"}
            </button>
            <p>{paused ? "Auto-scroll paused on hover" : manualPaused ? "Scroll manually paused" : "Auto-scroll active"}</p>
          </div>
        </div>

        {connectionError ? (
          <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{connectionError}</p>
        ) : null}

        <div
          ref={logViewportRef}
          className="mt-6 h-[520px] overflow-auto rounded-[28px] border border-ink/10 bg-ink p-4 font-mono text-sm text-mist shadow-inner"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
        >
          <div className="space-y-2">
            {filteredLines.map((line) => (
              <div
                key={line.id}
                className={cn(
                  "rounded-2xl px-3 py-2 whitespace-pre-wrap break-words",
                  line.level === "ERROR" || line.level === "FATAL"
                    ? "bg-coral/15 text-[#ffd6c8]"
                    : line.level === "WARN" || line.level === "WARNING"
                      ? "bg-[#f5b971]/12 text-[#ffe3b8]"
                      : line.level === "INFO"
                        ? "bg-white/5"
                        : "bg-transparent",
                )}
              >
                <div className="flex flex-wrap items-start gap-3">
                  {line.level ? (
                    <span className="mt-0.5 rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold tracking-[0.18em] text-mist/70">
                      {line.level}
                    </span>
                  ) : null}
                  <span className="flex-1 leading-6">{line.raw}</span>
                </div>
              </div>
            ))}
            {!filteredLines.length ? (
              <p className="rounded-2xl bg-white/5 px-4 py-3 text-mist/60">
                {totalCount ? "No log lines match the current filters." : "Waiting for log output..."}
              </p>
            ) : null}
          </div>
        </div>
      </Card>
    </div>
  );
}
