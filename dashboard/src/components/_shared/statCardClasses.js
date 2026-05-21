/**
 * Shared stat card / number tile styling constants — single source of truth
 * for the little rectangles that show a number + label across the dashboard.
 *
 * Sibling to tabClasses.js. Same rule: every stat card MUST use these
 * constants OR the <StatCard> component (which imports these under the hood).
 * Never write bespoke padding/font/border combinations.
 *
 * Why constants alongside the component:
 * - Existing pages with custom layouts (progress bars, sub-stats, multi-line
 *   meta) can use the constants without forcing a refactor into <StatCard>'s
 *   prop shape.
 * - Simple cases (label + number) should use <StatCard> directly.
 *
 * Audit (2026-05-21) found 31 stat cards across 7 files with the SAME
 * intent but drifting in: font-weight (bold vs semibold), label transform
 * (UPPERCASE vs none), label size (text-xs vs text-sm vs text-[10px]),
 * dark-mode coverage (partial). This file is the cure.
 *
 * Intentionally NO left-border-color accent and NO left-padded icon.
 * Per user feedback: "too many number cards have same icon in left
 * padding/border — don't repeat that pattern." Keep stat cards clean.
 */

// Card container. Apply to the outer <div>.
// Border + background + padding + radius. No left accent, no icon slot.
export const STAT_CARD_BASE = 'rounded-lg border border-gray-200 bg-white p-4';

// Label (small text above the number, e.g. "TEAMS").
export const STAT_LABEL = 'text-xs font-medium uppercase tracking-wide text-gray-500';

// Number (big text, the metric value).
export const STAT_NUMBER = 'mt-1 text-2xl font-bold text-gray-900';

// Sub-line beneath the number (e.g. "12 active · 3 archived"). Optional.
export const STAT_SUBLINE = 'mt-1 text-xs text-gray-400';

// Number color variants — apply IN PLACE OF the default text-gray-900.
// Use `tokens` of intent, not bare colors, so we can re-theme later.
export const STAT_NUMBER_COLORS = {
	default: 'text-gray-900',
	good:    'text-green-600',   // healthy / success counts
	warn:    'text-amber-600',   // attention / borderline
	bad:     'text-red-600',     // failures / critical
	info:    'text-blue-600',    // neutral metric (monetary, count of N)
	muted:   'text-gray-500',    // greyed-out / zero state
};

/**
 * Build the number's class string. Combines STAT_NUMBER + color variant.
 * Usage: `:class="statNumberClass('good')"`
 */
export function statNumberClass(color = 'default') {
	return `${STAT_NUMBER.replace(' text-gray-900', '')} ${STAT_NUMBER_COLORS[color] || STAT_NUMBER_COLORS.default}`;
}

/**
 * Grid container for a row of cards. Responsive: 2 col mobile, up to 6 desktop.
 * Apply to the parent <div> that wraps multiple StatCards.
 */
export const STAT_CARD_GRID = 'grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5';
