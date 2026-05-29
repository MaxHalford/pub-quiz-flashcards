<script lang="ts">
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { loadState, saveState } from '$lib/storage';
  import { loadCards, sourceLabel } from '$lib/cards';
  import SourceRow from '$lib/components/SourceRow.svelte';
  import TopicPill from '$lib/components/TopicPill.svelte';

  let cardCount = $state(0);
  let deviceId = $state('');
  let sourceCounts = $state<Array<{ source: string; count: number }>>([]);
  let topicCounts = $state<Array<{ topic: string; count: number }>>([]);
  let disabledSources = $state<Record<string, true>>({});
  let disabledTopics = $state<Record<string, true>>({});

  $effect(() => {
    const s = loadState();
    cardCount = Object.keys(s.cards).length;
    deviceId = s.deviceId;
    disabledSources = { ...(s.settings.disabledSources ?? {}) };
    disabledTopics = { ...(s.settings.disabledTopics ?? {}) };
  });
  onMount(async () => {
    const { cards } = await loadCards();
    const srcCounts = new Map<string, number>();
    const tpcCounts = new Map<string, number>();
    for (const c of cards) {
      srcCounts.set(c.source, (srcCounts.get(c.source) ?? 0) + 1);
      if (c.topic) tpcCounts.set(c.topic, (tpcCounts.get(c.topic) ?? 0) + 1);
    }
    sourceCounts = [...srcCounts.entries()]
      .map(([source, count]) => ({ source, count }))
      .sort((a, b) => sourceLabel(a.source).localeCompare(sourceLabel(b.source)));
    // Sort topics by count desc — most-populous buckets read first.
    topicCounts = [...tpcCounts.entries()]
      .map(([topic, count]) => ({ topic, count }))
      .sort((a, b) => b.count - a.count);
  });

  function toggleSource(source: string, enabled: boolean) {
    if (sourceCounts.length === 0) return;
    const next = { ...disabledSources };
    if (enabled) delete next[source];
    else next[source] = true;
    if (Object.keys(next).length >= sourceCounts.length) return;
    disabledSources = next;
    const s = loadState();
    s.settings.disabledSources = next;
    s.daily.queue = [];
    saveState(s);
  }

  function toggleTopic(topic: string, enabled: boolean) {
    const next = { ...disabledTopics };
    if (enabled) delete next[topic];
    else next[topic] = true;
    disabledTopics = next;
    const s = loadState();
    s.settings.disabledTopics = next;
    s.daily.queue = [];
    saveState(s);
  }
</script>

<main class="mx-auto flex min-h-[100dvh] max-w-md flex-col px-6 pt-safe-10 pb-safe-10">
  <header class="flex items-center justify-between">
    <a class="text-sm text-(--color-muted) hover:text-(--color-ink)" href="{base}/">← Back</a>
    <h1 class="font-serif text-lg">Settings</h1>
    <span class="w-12"></span>
  </header>

  <section class="mt-10 space-y-6">
    {#if sourceCounts.length > 0}
      <div>
        <h2 class="font-serif text-xl">Sources</h2>
        <p class="mt-1 text-sm text-(--color-muted)">
          Choose which sources to draw flashcards from. Changes apply on your next session.
        </p>
        <div class="mt-4 space-y-2">
          {#each sourceCounts as { source, count } (source)}
            {@const enabled = !disabledSources[source]}
            {@const locked = enabled && sourceCounts.length - Object.keys(disabledSources).length === 1}
            <SourceRow
              {source}
              {count}
              checked={enabled}
              disabled={locked}
              onchange={(c) => toggleSource(source, c)}
            />
          {/each}
        </div>
      </div>
    {/if}

    {#if topicCounts.length > 0}
      <div>
        <h2 class="font-serif text-xl">Topics</h2>
        <p class="mt-1 text-sm text-(--color-muted)">
          Hide topics you're not interested in. Untagged questions always come through.
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          {#each topicCounts as { topic, count } (topic)}
            <TopicPill
              label={topic}
              {count}
              enabled={!disabledTopics[topic]}
              onToggle={(e) => toggleTopic(topic, e)}
            />
          {/each}
        </div>
      </div>
    {/if}

    <div class="border-t border-(--color-muted)/20 pt-6 text-xs text-(--color-muted)">
      <p>Cards reviewed: {cardCount}</p>
      <p class="mt-1 font-mono">Device: {deviceId.slice(0, 8)}…</p>
    </div>

    <div class="border-t border-(--color-muted)/20 pt-6 text-xs text-(--color-muted)">
      <p>
        Made by <a
          class="underline hover:text-(--color-ink)"
          href="https://maxhalford.github.io/"
          target="_blank"
          rel="noopener noreferrer">Max Halford</a
        >.
      </p>
      <p class="mt-1">
        Source on <a
          class="underline hover:text-(--color-ink)"
          href="https://github.com/MaxHalford/pub-quiz-flashcards"
          target="_blank"
          rel="noopener noreferrer">GitHub</a
        >.
      </p>
      <p class="mt-1">
        Questions or feedback? <a
          class="underline hover:text-(--color-ink)"
          href="mailto:maxhalford25@gmail.com">maxhalford25@gmail.com</a
        >
      </p>
    </div>
  </section>
</main>
