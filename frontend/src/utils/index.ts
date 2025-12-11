/**
 * Utility functions for Belly-Buzz.
 */

/**
 * Convert price tier to dollar signs display.
 */
export function getPriceDisplay(tier: number): string {
  return '$'.repeat(tier);
}

/**
 * Format date for display.
 */
export function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(dateStr));
}

/**
 * Truncate text with ellipsis.
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '...';
}
