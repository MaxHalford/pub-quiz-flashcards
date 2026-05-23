import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRAPE_DIR = join(__dirname, '..', 'scrape');
const STATIC_DIR = join(__dirname, 'static');
const ANNOTATIONS_FILE = join(SCRAPE_DIR, 'wikipedia_annotations.json');

// Span tuple: [start, end, title_idx_into_titles_table]
type SpanTuple = [number, number, number];
type Annotation = { q?: SpanTuple[]; a?: SpanTuple[] };
type AnnotationsFile = { titles: string[]; cards: Record<string, Annotation> };
type Card = {
  id: string;
  q: string;
  a: string;
  source: string;
  source_date: string;
  source_url: string;
  tier?: string;
  qe?: SpanTuple[];
  ae?: SpanTuple[];
};
type CardsFile = { titles: string[]; cards: Card[] };

function shortId(sourceUrl: string, question: string): string {
  return createHash('sha1').update(`${sourceUrl}\n${question}`).digest('hex').slice(0, 12);
}

function contentHash(payload: string): string {
  return createHash('sha256').update(payload).digest('hex').slice(0, 10);
}

async function loadAnnotations(): Promise<AnnotationsFile> {
  if (!existsSync(ANNOTATIONS_FILE)) return { titles: [], cards: {} };
  const raw = await readFile(ANNOTATIONS_FILE, 'utf8');
  return JSON.parse(raw) as AnnotationsFile;
}

function buildCard(args: {
  source: string;
  source_url: string;
  source_date: string;
  question: string;
  answer: string;
  tier?: string | null;
  annotations: Record<string, Annotation>;
}): Card {
  const id = shortId(args.source_url, args.question);
  const ann = args.annotations[id];
  const card: Card = {
    id,
    q: args.question,
    a: args.answer,
    source: args.source,
    source_date: args.source_date,
    source_url: args.source_url
  };
  if (args.tier) card.tier = args.tier;
  if (ann?.q?.length) card.qe = ann.q;
  if (ann?.a?.length) card.ae = ann.a;
  return card;
}

async function readEntries<T>(source: string): Promise<T[] | null> {
  const path = join(SCRAPE_DIR, source, 'questions.json');
  if (!existsSync(path)) return null;
  const raw = await readFile(path, 'utf8');
  return JSON.parse(raw) as T[];
}

// --- per-source loaders ----------------------------------------------------

type GuardianEntry = {
  source_date: string;
  source_url: string;
  pairs: Array<{ question: string; answer: string }>;
};

async function loadGuardian(annotations: Record<string, Annotation>): Promise<Card[]> {
  const entries = await readEntries<GuardianEntry>('the_guardian_weekly');
  if (!entries) return [];
  const cards: Card[] = [];
  for (const entry of entries) {
    for (const pair of entry.pairs) {
      cards.push(
        buildCard({
          source: 'the_guardian_weekly',
          source_url: entry.source_url,
          source_date: entry.source_date,
          question: pair.question,
          answer: pair.answer,
          annotations
        })
      );
    }
  }
  return cards;
}

type Jeu1000EurosEntry = {
  id: string;
  date: string;
  title: string;
  url: string;
  pairs: Array<{ question: string; answer: string | null; tier: string | null }>;
};

async function loadJeu1000Euros(annotations: Record<string, Annotation>): Promise<Card[]> {
  const entries = await readEntries<Jeu1000EurosEntry>('le_jeu_des_1000_euros');
  if (!entries) return [];
  const cards: Card[] = [];
  for (const entry of entries) {
    for (const pair of entry.pairs) {
      // Skip pairs whose answer was never stated in the transcript — they
      // exist in the JSON for human review, not for the flashcard front-end.
      if (pair.answer == null) continue;
      cards.push(
        buildCard({
          source: 'le_jeu_des_1000_euros',
          source_url: entry.url,
          source_date: entry.date,
          question: pair.question,
          answer: pair.answer,
          tier: pair.tier,
          annotations
        })
      );
    }
  }
  return cards;
}

const LOADERS: Record<string, (annotations: Record<string, Annotation>) => Promise<Card[]>> = {
  the_guardian_weekly: loadGuardian,
  le_jeu_des_1000_euros: loadJeu1000Euros
};

// --- main ------------------------------------------------------------------

async function main() {
  const { titles, cards: annotations } = await loadAnnotations();
  const annotatedCount = Object.keys(annotations).length;

  // Warn about scrape dirs without a loader so a new source isn't silently dropped.
  const onDisk = (await readdir(SCRAPE_DIR, { withFileTypes: true }))
    .filter((d) => d.isDirectory() && !d.name.startsWith('.') && !d.name.startsWith('_'))
    .map((d) => d.name);
  for (const name of onDisk) {
    if (!(name in LOADERS)) console.warn(`  ${name}: no loader registered, skipping`);
  }

  const all: Card[] = [];
  for (const [name, loader] of Object.entries(LOADERS)) {
    const cards = await loader(annotations);
    all.push(...cards);
    console.log(`  ${name}: ${cards.length} cards`);
  }

  const dedup = new Map<string, Card>();
  for (const c of all) dedup.set(c.id, c);
  const cards = [...dedup.values()].sort((a, b) => a.id.localeCompare(b.id));

  const out: CardsFile = { titles, cards };
  const payload = JSON.stringify(out);
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
