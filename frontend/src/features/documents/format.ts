import { formatDateParts } from "@/lib/regional";

export function formatSize(octets: number): string {
  return octets < 1024 * 1024
    ? `${Math.max(1, Math.round(octets / 1024))} Ko`
    : `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? "Date inconnue"
    : formatDateParts(date, { dateStyle: "medium", timeStyle: "short" });
}
