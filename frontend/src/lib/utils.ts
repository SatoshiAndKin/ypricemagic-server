export function escapeHtml(str: string | null | undefined): string {
  if (str == null) return '';
  return String(str).replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[c] ?? c
  );
}

export function formatRelativeAge(timestamp: number | null): string {
  if (timestamp == null) return 'unknown';
  const diff = Math.floor(Date.now() / 1000) - timestamp;
  if (diff < 0) return 'just now';
  if (diff < 60) return diff + 's ago';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

export function formatTimestamp(timestamp: number | null): string {
  if (timestamp == null) return 'unknown';
  return new Date(timestamp * 1000).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
}
