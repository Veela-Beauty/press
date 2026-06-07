// Pure view-model helpers for the Notifications feed. No Vue, no I/O: unit-testable.
//
// The backend `press.api.notifications.get_notifications` returns rows shaped:
//   { name, type, read, title, message, creation, is_addressed, is_actionable,
//     document_type, document_name, route }
// It has NO severity field, so we infer one for the icon tint + severity chip.
import dayjs from '../../utils/dayjs';

// INTERIM severity inference. The Press Notification doctype has no severity
// field, so we classify from the type/title text here on the client. When a
// real `severity` column is added to get_notifications, delete this and read
// `n.severity` directly (see code-review 2026-06-07, Architecture-2B).
// Order matters: the first matching pattern wins (Error before Warning).
const SEVERITY_PATTERNS = [
  ['Error', /(fail|error|crash|\boom\b|denied|exceeded|unreachable|rolled back|\bdown\b)/],
  ['Warning', /(warn|validation|uncommitted|pending|requested|expir|retry|throttl)/],
  ['Success', /(complete|success|recovered|recovery|upgraded|finished|restored|scaled|online|deployed)/],
];
export function severityOf(n) {
  const t = `${n.type || ''} ${n.title || ''}`.toLowerCase();
  for (const [severity, pattern] of SEVERITY_PATTERNS) {
    if (pattern.test(t)) return severity;
  }
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

// Relative "2 hours ago" label. Reuses the dashboard's dayjs instance (already
// extended with the relativeTime plugin) for locale-correct output.
export function timeAgo(creation, now = new Date()) {
  if (!creation) return '';
  const d = dayjs(String(creation).replace(' ', 'T'));
  if (!d.isValid()) return '';
  return d.from(dayjs(now));
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
