import { useEffect, useMemo, useState } from "react";
import type { HRVDashboardPayload, HRVSample, RecoveryEvent } from "../lib/types";
import { useMockHRVStream } from "./useMockHRVStream";

const DEFAULT_STREAM_URL = "http://127.0.0.1:8765/stream";

function streamUrl(): string {
  const configured = import.meta.env.VITE_HRV_STREAM_URL;
  return typeof configured === "string" && configured.trim() ? configured.trim() : DEFAULT_STREAM_URL;
}

export function useHRVStream(): {
  currentPayload: HRVDashboardPayload;
  history: HRVSample[];
  events: RecoveryEvent[];
  isLive: boolean;
} {
  const mock = useMockHRVStream();
  const [livePayload, setLivePayload] = useState<HRVDashboardPayload | null>(null);
  const [liveHistory, setLiveHistory] = useState<HRVSample[]>([]);
  const [isLive, setIsLive] = useState(false);
  const url = useMemo(streamUrl, []);

  useEffect(() => {
    const source = new EventSource(url);

    source.onopen = () => {
      setIsLive(true);
    };

    source.addEventListener("hrv", (event) => {
      try {
        const next = JSON.parse(event.data) as HRVDashboardPayload;
        setLivePayload(next);
        setLiveHistory((items) => [...items, next.sample]);
        setIsLive(true);
      } catch (error) {
        console.warn("Ignoring malformed HRV stream payload", error);
      }
    });

    source.onerror = () => {
      setIsLive(false);
    };

    return () => {
      source.close();
    };
  }, [url]);

  if (livePayload === null) {
    return { ...mock, isLive: false };
  }

  return {
    currentPayload: livePayload,
    history: liveHistory.length > 0 ? liveHistory : [livePayload.sample],
    events: livePayload.events,
    isLive,
  };
}
