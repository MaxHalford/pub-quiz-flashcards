import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRAPE_DIR = join(__dirname, '..', 'scrape');
const STATIC_DIR = join(__dirname, 'static');
const ANNOTATIONS_FILE = join(SCRAPE_DIR, 'wikipedia_annotations.json');

type Pair = { question: string; answer: string };
type Entry = { pairs: Pair[]; source_date: string; source_url: string };
type EntitySpan = { start: number; end: number; title: string; url: string };
type Annotation = { q_entities?: EntitySpan[]; a_entities?: EntitySpan[] };
type Card = {
  id: string;
  q: string;
  a: string;
  source: string;
  source_date: string;
  source_url: string;
  q_entities?: EntitySpan[];
  a_entities?: EntitySpan[];
};

function shortId(sourceUrl: string, question: string): string {
  return createHash('sha1').update(`${sourceUrl}\n${question}`).digest('hex').slice(0, 12);
}

function contentHash(payload: string): string {
  return createHash('sha256').update(payload).digest('hex').slice(0, 10);
}

async function loadAnnotations(): Promise<Record<string, Annotation>> {
  if (!existsSync(ANNOTATIONS_FILE)) return {};
  const raw = await readFile(ANNOTATIONS_FILE, 'utf8');
  return JSON.parse(raw) as Record<string, Annotation>;
}

async function loadSource(name: string, annotations: Record<string, Annotation>): Promise<Card[]> {
  const path = join(SCRAPE_DIR, name, 'questions.json');
  if (!existsSync(path)) return [];
  const raw = await readFile(path, 'utf8');
  const entries: Entry[] = JSON.parse(raw);
  const cards: Card[] = [];
  const seen = new Set<string>();
  for (const entry of entries) {
    for (const pair of entry.pairs) {
      const id = shortId(entry.source_url, pair.question);
      if (seen.has(id)) continue;
      seen.add(id);
      const ann = annotations[id];
      const card: Card = {
        id,
        q: pair.question,
        a: pair.answer,
        source: name,
        source_date: entry.source_date,
        source_url: entry.source_url
      };
      if (ann?.q_entities?.length) card.q_entities = ann.q_entities;
      if (ann?.a_entities?.length) card.a_entities = ann.a_entities;
      cards.push(card);
    }
  }
  return cards;
}

async function main() {
  const annotations = await loadAnnotations();
  const annotatedCount = Object.keys(annotations).length;

  const sourceDirs = (await readdir(SCRAPE_DIR, { withFileTypes: true }))
    .filter((d) => d.isDirectory() && !d.name.startsWith('.') && !d.name.startsWith('_'))
    .map((d) => d.name)
    .sort();

  const all: Card[] = [];
  for (const name of sourceDirs) {
    const cards = await loadSource(name, annotations);
    all.push(...cards);
    console.log(`  ${name}: ${cards.length} cards`);
  }

  const dedup = new Map<string, Card>();
  for (const c of all) dedup.set(c.id, c);
  const cards = [...dedup.values()].sort((a, b) => a.id.localeCompare(b.id));

  const payload = JSON.stringify(cards);
  const hash = contentHash(payload);
  const generatedAt = new Date().toISOString();

  const old = (await readdir(STATIC_DIR)).filter((f) => /^cards\.[a-f0-9]+\.json$/.test(f));
  for (const f of old) await rm(join(STATIC_DIR, f));

  await writeFile(join(STATIC_DIR, `cards.${hash}.json`), payload);
  await writeFile(
    join(STATIC_DIR, 'cards-manifest.json'),
    JSON.stringify({ hash, count: cards.length, generatedAt }, null, 2) + '\n'
  );

  console.log(
    `Wrote cards.${hash}.json (${cards.length} cards, ${(payload.length / 1024).toFixed(0)} KB, ${annotatedCount} annotated)`
  );
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
