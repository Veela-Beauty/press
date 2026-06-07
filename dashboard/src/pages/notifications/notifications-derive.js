// Pure view-model helpers for the Notifications feed. No Vue, no I/O: unit-testable.
//
// The backend `press.api.notifications.get_notifications` returns rows shaped:
//   { name, type, read, title, message, creation, is_addressed, is_actionable,
//     document_type, document_name, route }
// It has NO severity field, so we infer one for the icon tint + severity chip.

// Coarse severity from the type/title text. Order matters: error wins over warning.
export function severityOf(n) {
  const t = `${n.type || ''} ${n.title || ''}`.toLowerCase();
  if (/(fail|error|crash|\boom\b|denied|exceeded|unreachable|rolled back|\bdown\b)/.test(t)) return 'Error';
  if (/(warn|validation|uncommitted|pending|requested|expir|retry|throttl)/.test(t)) return 'Warning';
  if (/(complete|success|recovered|recovery|upgraded|finished|restored|scaled|online|deployed)/.test(t)) return 'Success';
  return 'Info';
}

// Does this notification need the user to act? (real fields, not inferred)
export function needsAttention(n) {
  return !!(n.is_actionable && !n.is_addressed);
}

// Bucket a creation timestamp into Today / Yesterday / Earlier (local time).
export function bucketOf(creation, now = new Date()) {
  if (!creation) return 'Earlier';
  const d = new Date(String(creation).replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return 'Earlier';
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startYesterday = new Date(startToday);
  startYesterday.setDate(startYesterday.getDate() - 1);
  if (d >= startToday) return 'Today';
  if (d >= startYesterday) return 'Yesterday';
  return 'Earlier';
}

// Relative "2h ago" label.
export function timeAgo(creation, now = new Date()) {
  if (!creation) return '';
  const d = new Date(String(creation).replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return '';
  const s = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`;
  const dd = Math.floor(h / 24); if (dd < 30) return `${dd}d ago`;
  const mo = Math.floor(dd / 30); if (mo < 12) return `${mo}mo ago`;
  return `${Math.floor(mo / 12)}y ago`;
}

// Strip every HTML tag except <b> from the message (mirrors the old ObjectList).
export function cleanMessage(message) {
  if (!message) return '';
  return String(message).replace(/<(?!\/?b\b)[^>]*>/g, '').trim();
}

// Plain-text length, used to decide whether the "Show more" toggle is needed.
export function plainLength(message) {
  return cleanMessage(message).replace(/<[^>]+>/g, '').length;
}

// Summary counts for the chips.
export function summarize(items) {
  return {
    unread: items.filter((n) => !n.read).length,
    attention: items.filter(needsAttention).length,
    errors: items.filter((n) => severityOf(n) === 'Error').length,
  };
}

// Apply the active tab + type + severity filters.
export function applyFilters(items, { tab, type, severity }) {
  return items.filter((n) => {
    if (tab === 'unread' && n.read) return false;
    if (tab === 'attention' && !needsAttention(n)) return false;
    if (type && n.type !== type) return false;
    if (severity && severityOf(n) !== severity) return false;
    return true;
  });
}

// Group filtered items into the three ordered time buckets, dropping empties.
export function groupByBucket(items, now = new Date()) {
  const order = ['Today', 'Yesterday', 'Earlier'];
  const map = { Today: [], Yesterday: [], Earlier: [] };
  for (const n of items) map[bucketOf(n.creation, now)].push(n);
  return order.filter((label) => map[label].length).map((label) => ({ label, items: map[label] }));
}

// Distinct notification types present, for the type dropdown.
export function distinctTypes(items) {
  return [...new Set(items.map((n) => n.type).filter(Boolean))].sort();
}
