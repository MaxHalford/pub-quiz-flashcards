<script lang="ts">
  import SourceRow from './SourceRow.svelte';

  type Props = {
    sourceCounts: Array<{ source: string; count: number }>;
    onConfirm: (disabledSources: Record<string, true>) => void;
  };
  let { sourceCounts, onConfirm }: Props = $props();

  let selected = $state<Record<string, true>>({});

  const selectedCount = $derived(Object.keys(selected).length);

  function toggle(source: string, checked: boolean) {
    const next = { ...selected };
    if (checked) next[source] = true;
    else delete next[source];
    selected = next;
  }

  function confirm() {
    if (selectedCount === 0) return;
    const disabled: Record<string, true> = {};
    for (const { source } of sourceCounts) {
      if (!selected[source]) disabled[source] = true;
    }
    onConfirm(disabled);
  }
</script>

<main class="mx-auto flex min-h-[100dvh] max-w-md flex-col px-6 pt-safe-10 pb-safe-10">
  <header class="text-center">
    <p class="text-xs tracking-wider text-(--color-muted) uppercase">Welcome</p>
    <h1 class="mt-3 font-serif text-3xl leading-tight">Pub Quiz Flashcards</h1>
  </header>

  <section class="mt-10 space-y-4 font-serif text-lg leading-relaxed">
    <p>
      A daily helping of trivia, scraped from weekly quizzes around the web.
    </p>
    <p class="text-base text-(--color-muted)">
      You'll get asked 10 questions each day. Two buttons — <em>Know</em>
      and <em>Don't know</em> — schedule each card for its next review using
      <a
        class="underline decoration-(--color-accent)/50 underline-offset-[0.2em] hover:decoration-(--color-accent)"
        href="https://en.wikipedia.org/wiki/Spaced_repetition"
        target="_blank"
        rel="noopener">spaced repetition</a
      >. Progress lives only in your browser.
    </p>
    <p class="text-base text-(--color-muted)">
      Built by <a
        class="underline decoration-(--color-accent)/50 underline-offset-[0.2em] hover:decoration-(--color-accent)"
        href="https://maxhalford.github.io"
        target="_blank"
        rel="noopener">Max Halford</a
      >. Open source on
      <a
        class="underline decoration-(--color-accent)/50 underline-offset-[0.2em] hover:decoration-(--color-accent)"
        href="https://github.com/MaxHalford/pub-quiz-flashcards"
        target="_blank"
        rel="noopener">GitHub</a
      >.
    </p>
  </section>

  <section class="mt-10">
    <h2 class="font-serif text-xl">Choose your decks</h2>
    <p class="mt-1 text-sm text-(--color-muted)">
      Pick the sources you want questions drawn from. You can change this later.
    </p>
    <div class="mt-4 space-y-2">
      {#each sourceCounts as { source, count } (source)}
        <SourceRow
          {source}
          {count}
          checked={!!selected[source]}
          onchange={(c) => toggle(source, c)}
        />
      {/each}
    </div>
  </section>

  <footer class="mt-auto pt-10">
    <button
      class="w-full rounded-2xl bg-(--color-ink) px-6 py-4 text-base font-medium text-(--color-paper) transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
      disabled={selectedCount === 0}
      onclick={confirm}
    >
      {selectedCount === 0 ? 'Pick at least one deck' : 'Start'}
    </button>
  </footer>
</main>
