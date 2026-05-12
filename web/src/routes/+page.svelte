<script lang="ts">
  import { onMount } from 'svelte';
  import { base } from '$app/paths';

  let count = $state<number | null>(null);
  let generatedAt = $state<string | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      const manifestRes = await fetch(`${base}/cards-manifest.json`, { cache: 'no-cache' });
      if (!manifestRes.ok) throw new Error(`manifest ${manifestRes.status}`);
      const manifest = await manifestRes.json();
      generatedAt = manifest.generatedAt;
      const cardsRes = await fetch(`${base}/cards.${manifest.hash}.json`);
      if (!cardsRes.ok) throw new Error(`cards ${cardsRes.status}`);
      const cards = await cardsRes.json();
      count = cards.length;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  });
</script>

<main class="mx-auto flex min-h-[100dvh] max-w-md flex-col items-center justify-center px-6 py-12 text-center">
  <h1 class="font-serif text-4xl tracking-tight">Pub Quiz Flashcards</h1>
  <p class="mt-4 text-sm text-(--color-muted)">
    {#if error}
      <span class="text-(--color-accent)">Failed to load: {error}</span>
    {:else if count === null}
      Loading…
    {:else}
      Loaded {count.toLocaleString()} cards.
    {/if}
  </p>
  {#if generatedAt}
    <p class="mt-1 text-xs text-(--color-muted)/70">Built {generatedAt}</p>
  {/if}
</main>
