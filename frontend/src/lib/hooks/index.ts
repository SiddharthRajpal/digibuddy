/**
 * Data hooks. Pages and components never call fetch directly: they use these hooks,
 * so presentation can change without touching data flow.
 */
"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  CheckIn,
  CheckInCreate,
  CheckInPatch,
  CheckInResult,
  Insights,
  Meta,
  Metric,
  MetricBody,
  MetricPatch,
  PredictionHistory,
  Tomorrow,
  Twin,
  User,
  UserPatch,
} from "@/types/api";

export const keys = {
  tomorrow: ["predictions", "tomorrow"] as const,
  history: (from?: string, to?: string) => ["predictions", "history", from, to] as const,
  checkins: (from?: string, to?: string) => ["checkins", "list", from, to] as const,
  checkin: (date: string) => ["checkins", "one", date] as const,
  twin: ["twin"] as const,
  insights: ["insights"] as const,
  metrics: ["metrics"] as const,
  meta: ["meta"] as const,
};

function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v) as [string, string][];
  return entries.length ? `?${new URLSearchParams(entries).toString()}` : "";
}

function useAuthed(): boolean {
  return useAuth().status === "authenticated";
}

// --- reads ------------------------------------------------------------------------------

export function useTomorrow(): UseQueryResult<Tomorrow> {
  return useQuery({
    queryKey: keys.tomorrow,
    queryFn: () => apiFetch<Tomorrow>("/predictions/tomorrow"),
    enabled: useAuthed(),
  });
}

export function usePredictionHistory(from?: string, to?: string): UseQueryResult<PredictionHistory> {
  return useQuery({
    queryKey: keys.history(from, to),
    queryFn: () => apiFetch<PredictionHistory>(`/predictions/history${qs({ from, to })}`),
    enabled: useAuthed(),
  });
}

export function useCheckins(from?: string, to?: string): UseQueryResult<CheckIn[]> {
  return useQuery({
    queryKey: keys.checkins(from, to),
    queryFn: () => apiFetch<CheckIn[]>(`/checkins${qs({ from, to })}`),
    enabled: useAuthed(),
  });
}

/** One check-in, or `null` when that day has none yet. */
export function useCheckin(date: string): UseQueryResult<CheckIn | null> {
  return useQuery({
    queryKey: keys.checkin(date),
    queryFn: async () => {
      try {
        return await apiFetch<CheckIn>(`/checkins/${date}`);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    enabled: useAuthed() && /^\d{4}-\d{2}-\d{2}$/.test(date),
  });
}

export function useTwin(): UseQueryResult<Twin> {
  return useQuery({ queryKey: keys.twin, queryFn: () => apiFetch<Twin>("/twin"), enabled: useAuthed() });
}

export function useInsights(): UseQueryResult<Insights> {
  return useQuery({
    queryKey: keys.insights,
    queryFn: () => apiFetch<Insights>("/insights"),
    enabled: useAuthed(),
  });
}

export function useMetrics(): UseQueryResult<Metric[]> {
  return useQuery({
    queryKey: keys.metrics,
    queryFn: () => apiFetch<Metric[]>("/metrics"),
    enabled: useAuthed(),
  });
}

export function useMeta(): UseQueryResult<Meta> {
  return useQuery({
    queryKey: keys.meta,
    queryFn: () => apiFetch<Meta>("/meta"),
    enabled: useAuthed(),
    staleTime: Infinity,
  });
}

// --- writes -----------------------------------------------------------------------------

function useInvalidateDayData() {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["checkins"] }),
      qc.invalidateQueries({ queryKey: ["predictions"] }),
      qc.invalidateQueries({ queryKey: keys.twin }),
      qc.invalidateQueries({ queryKey: keys.insights }),
    ]);
}

export function useCreateCheckin() {
  const invalidate = useInvalidateDayData();
  return useMutation({
    mutationFn: (body: CheckInCreate) =>
      apiFetch<CheckInResult>("/checkins", { method: "POST", body }),
    onSuccess: invalidate,
  });
}

export function useUpdateCheckin(date: string) {
  const invalidate = useInvalidateDayData();
  return useMutation({
    mutationFn: (body: CheckInPatch) =>
      apiFetch<CheckIn>(`/checkins/${date}`, { method: "PATCH", body }),
    onSuccess: invalidate,
  });
}

export function useDeleteCheckin() {
  const invalidate = useInvalidateDayData();
  return useMutation({
    mutationFn: (date: string) => apiFetch<null>(`/checkins/${date}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function useUpdateMe() {
  const { setUser } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UserPatch) => apiFetch<User>("/me", { method: "PATCH", body }),
    onSuccess: (user) => {
      setUser(user);
      return qc.invalidateQueries();
    },
  });
}

export function useCreateMetric() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MetricBody) => apiFetch<Metric>("/metrics", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.metrics }),
  });
}

export function useUpdateMetric() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: MetricPatch & { id: number }) =>
      apiFetch<Metric>(`/metrics/${id}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.metrics }),
  });
}

export function useDeleteMetric() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<null>(`/metrics/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.metrics }),
  });
}

/** Downloads the user's data as a file (JSON of everything, or CSV of check-ins). */
export function useExport() {
  return useMutation({
    mutationFn: async (format: "json" | "csv") => {
      const res = await apiFetch<Response>(`/me/export?format=${format}`, { raw: true });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = format === "csv" ? "digibuddy-checkins.csv" : "digibuddy-export.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
  });
}

export function useDeleteAccount() {
  const { forget } = useAuth();
  return useMutation({
    mutationFn: () => apiFetch<null>("/me", { method: "DELETE" }),
    onSuccess: forget,
  });
}
