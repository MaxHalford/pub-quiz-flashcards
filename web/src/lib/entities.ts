import type { EntitySpan } from './types';

export type TextPart =
  | { kind: 'text'; text: string }
  | { kind: 'link'; text: string; title: string; url: string };

export function renderWithLinks(text: string, spans: EntitySpan[] | undefined): TextPart[] {
  if (!spans || spans.length === 0) return [{ kind: 'text', text }];
  const sorted = [...spans].sort((a, b) => a.start - b.start);
  const parts: TextPart[] = [];
  let cursor = 0;
  for (const span of sorted) {
    if (span.start < cursor) continue;
    if (cursor < span.start) {
      parts.push({ kind: 'text', text: text.slice(cursor, span.start) });
    }
    parts.push({
      kind: 'link',
      text: text.slice(span.start, span.end),
      title: span.title,
      url: span.url
    });
    cursor = span.end;
  }
  if (cursor < text.length) {
    parts.push({ kind: 'text', text: text.slice(cursor) });
  }
  return parts;
}
