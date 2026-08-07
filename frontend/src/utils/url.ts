/**
 * Returns true only for plain http(s) URLs.
 *
 * Used before rendering an `<a href>` built from scraped/LLM-derived data
 * (job postings, recruiter profile URLs, etc.) so a crafted value like
 * `javascript:...` can never be rendered as a clickable link.
 */
export function isSafeExternalUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}
