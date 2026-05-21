/**
 * Shared tab styling constants — single source of truth for top-bar tabs
 * across the entire dashboard. Any tabbed page that doesn't use the
 * <UnifiedTabs> component should import these classes inline so the
 * style stays consistent.
 *
 * Active state: bold + near-black text. NO underline, NO pill, NO shape change.
 * Inactive state: medium weight + gray-500 text, hover to gray-900.
 *
 * Why constants instead of a single component:
 * - Existing pages have icon/router/sidebar variations that don't fit
 *   one component cleanly (FontAwesome vs FeatherIcon, router-link vs
 *   button, top-bar vs sidebar).
 * - Inline classes are a 2-line diff per page; component refactor is
 *   60-200 lines per page with regression risk.
 * - New pages should use <UnifiedTabs> directly (it imports these
 *   constants under the hood).
 *
 * NEVER add a new tab pattern without either using these constants
 * or <UnifiedTabs>. If you find yourself writing a 4th color/size
 * variant, update this file instead.
 */

// Per-tab-button classes — apply to <button> or <router-link> directly.
// Combine with TAB_BUTTON_BASE.
export const TAB_BUTTON_BASE = 'flex items-center gap-2 px-4 py-2.5 text-sm transition';

export const TAB_BUTTON_ACTIVE = 'font-bold text-gray-900';

export const TAB_BUTTON_INACTIVE = 'font-medium text-gray-500 hover:text-gray-900';

// Container for the tab strip itself.
// Use TAB_STRIP_BASE on the row; TAB_STRIP_DIVIDER underneath when a body is open.
export const TAB_STRIP_BASE = 'flex items-center bg-gray-50 rounded-lg border border-gray-200 px-1';

// For "panel" style (tab strip inside a card with content below):
// rounded only on top, no rounded-lg + border around the whole thing.
export const TAB_STRIP_PANEL_TOP = 'flex items-center bg-gray-50';

export const TAB_STRIP_DIVIDER = 'border-b border-gray-200';

// Convenience helper: pick active or inactive based on bool.
// Usage: `:class="tabClass(activeTab === t.id)"`
export function tabClass(isActive) {
	return `${TAB_BUTTON_BASE} ${isActive ? TAB_BUTTON_ACTIVE : TAB_BUTTON_INACTIVE}`;
}
