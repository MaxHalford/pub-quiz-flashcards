<script lang="ts">
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { loadCards, sourceLabel } from '$lib/cards';
  import { loadState, saveState, ensureToday, todayKey } from '$lib/storage';
  import { planSession, applyRating } from '$lib/scheduler';
  import { streakDays } from '$lib/streak';
  import Streak from '$lib/components/Streak.svelte';
  import Heatmap from '$lib/components/Heatmap.svelte';
  import RichText from '$lib/components/RichText.svelte';
  import type { Card, AppState } from '$lib/types';

  let cardIndex = $state<Map<string, Card>>(new Map());
  let appState = $state<AppState | null>(null);
  let revealed = $state(false);
  let error = $state<string | null>(null);
  let loading = $state(true);

  const dailyGoalCap = $derived(
    appState ? appState.settings.dailyGoal * (1 + appState.daily.extras) : 10
  );
  const currentCard = $derived(
    appState && appState.daily.queue.length > 0
      ? (cardIndex.get(appState.daily.queue[0]) ?? null)
      : null
  );
  const sessionDone = $derived(
    appState !== null && currentCard === null && cardIndex.size > 0
  );
  const streak = $derived(appState ? streakDays(appState.history) : 0);

  onMount(async () => {
    try {
      const { cards } = await loadCards();
      cardIndex = new Map(cards.map((c) => [c.id, c]));
      const state = ensureToday(loadState());
      state.daily.queue = state.daily.queue.filter((id) => cardIndex.has(id));
      if (state.daily.queue.length === 0 && state.daily.reviewed < dailyGoalCapFor(state)) {
        const seen = new Set(state.daily.results.map((r) => r.id));
        state.daily.queue = planSession(cards, state, capRemaining(state), Date.now(), seen).map(
          (c) => c.id
        );
      }
      appState = state;
      saveState(appState);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  });

  function dailyGoalCapFor(s: AppState): number {
    return s.settings.dailyGoal * (1 + s.daily.extras);
  }

  function capRemaining(s: AppState): number {
    return Math.max(0, dailyGoalCapFor(s) - s.daily.reviewed);
  }

  function rate(knew: boolean) {
    if (!appState || !currentCard) return;
    const updated = applyRating(appState.cards[currentCard.id], knew);
    appState.cards[currentCard.id] = updated;
    appState.daily.reviewed += 1;
    appState.daily.results.push({ id: currentCard.id, knew });
    const today = todayKey();
    appState.history[today] = (appState.history[today] ?? 0) + 1;
    const seenTitles = new Set(appState.daily.entities.map((e) => e.title));
    for (const span of [
      ...(currentCard.q_entities ?? []),
      ...(currentCard.a_entities ?? [])
    ]) {
      if (!seenTitles.has(span.title)) {
        seenTitles.add(span.title);
        appState.daily.entities.push({ title: span.title, url: span.url });
      }
    }
    appState.daily.queue.shift();
    revealed = false;
    saveState(appState);
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
      navigator.vibrate(8);
    }
  }

  function keepGoing() {
    if (!appState) return;
    appState.daily.extras += 1;
    revealed = false;
    const cards = [...cardIndex.values()];
    const seen = new Set(appState.daily.results.map((r) => r.id));
    appState.daily.queue = planSession(
      cards,
      appState,
      capRemaining(appState),
      Date.now(),
      seen
    ).map((c) => c.id);
    saveState(appState);
  }
</script>

<main class="mx-auto flex min-h-[100dvh] max-w-md flex-col px-6 pt-safe-6 pb-safe-6">
  <nav class="flex items-center justify-between">
    <Streak count={streak} />
    <a
      href="{base}/settings"
      class="rounded-full p-2 text-(--color-muted) transition hover:text-(--color-ink)"
      aria-label="Settings"
    >
      <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
      </svg>
    </a>
  </nav>

  {#if loading}
    <p class="m-auto text-sm text-(--color-muted)">Loading…</p>
  {:else if error}
    <p class="m-auto text-center text-sm text-(--color-accent)">Failed to load: {error}</p>
  {:else if !appState}
    <p class="m-auto text-sm text-(--color-muted)">No state.</p>
  {:else if sessionDone}
    <div class="w-full pt-16 text-center">
      <p class="font-serif text-4xl tracking-tight">That's all for today.</p>
      <p class="mt-3 text-sm text-(--color-muted)">
        {appState.daily.reviewed} answered. See you tomorrow.
      </p>

      <div class="mt-12 flex justify-center">
        <Heatmap history={appState.history} />
      </div>

      <button
        class="mt-12 rounded-full bg-(--color-ink) px-6 py-3 text-sm font-medium text-(--color-paper) transition active:scale-95"
        onclick={keepGoing}
      >
        Keep going (+{appState.settings.dailyGoal})
      </button>

      {#if appState.daily.entities.length > 0}
        <div class="mt-12 text-left">
          <p class="text-xs tracking-wider text-(--color-muted) uppercase">Mentioned today</p>
          <ul class="mt-4 space-y-2 text-lg leading-snug">
            {#each appState.daily.entities as e (e.title)}
              <li>
                <a
                  href={e.url}
                  target="_blank"
                  rel="noopener"
                  class="decoration-(--color-accent)/50 decoration-1 underline underline-offset-[0.2em] hover:decoration-(--color-accent) hover:decoration-2"
                  >{e.title}</a
                >
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  {:else if currentCard}
    {@const batchStart = appState.daily.extras * appState.settings.dailyGoal}
    {@const batchResults = appState.daily.results.slice(batchStart)}
    <header class="mt-4 flex items-center justify-between text-xs text-(--color-muted)">
      <span>Question {appState.daily.reviewed + 1} of {dailyGoalCap}</span>
      <span class="flex items-center gap-1.5">
        {#each Array.from({ length: appState.settings.dailyGoal }) as _, i (i)}
          {@const r = batchResults[i]}
          <span
            class="block h-2 w-2 rounded-full border border-(--color-muted)/40"
            style:background-color={r === undefined
              ? 'transparent'
              : r.knew
                ? 'var(--color-ink)'
                : 'color-mix(in srgb, var(--color-muted) 30%, transparent)'}
            style:border-color={r === undefined ? undefined : 'transparent'}
          ></span>
        {/each}
      </span>
    </header>

    <section class="flex min-h-0 flex-1 flex-col overflow-hidden pt-8">
      <p class="pb-6 font-serif text-2xl leading-snug">
        <RichText text={currentCard.q} spans={currentCard.q_entities} linkable={revealed} />
      </p>
      <div class="min-h-0 flex-1 overflow-hidden border-t border-(--color-muted)/20 pt-6">
        {#key currentCard.id}
          <div
            class="transition duration-200"
            class:opacity-0={!revealed}
            class:translate-y-2={!revealed}
            aria-hidden={!revealed}
          >
            <p class="font-serif text-2xl leading-snug text-(--color-accent)">
              <RichText text={currentCard.a} spans={currentCard.a_entities} />
            </p>
            <a
              class="mt-4 inline-block text-xs text-(--color-muted) underline-offset-4 hover:underline"
              href={currentCard.source_url}
              target="_blank"
              rel="noopener"
              tabindex={revealed ? 0 : -1}
            >
              {sourceLabel(currentCard.source)}, {currentCard.source_date}
            </a>
          </div>
        {/key}
      </div>
    </section>

    <footer class="mt-auto pt-8">
      {#if !revealed}
        <button
          class="w-full rounded-2xl border border-transparent bg-(--color-ink) px-6 py-4 text-base font-medium text-(--color-paper) transition active:scale-[0.98]"
          onclick={() => (revealed = true)}
        >
          Show answer
        </button>
      {:else}
        <div class="grid grid-cols-2 gap-3">
          <button
            class="rounded-2xl border border-(--color-muted)/30 px-6 py-4 text-base font-medium transition active:scale-[0.98]"
            onclick={() => rate(false)}
          >
            Don't know
          </button>
          <button
            class="rounded-2xl border border-transparent bg-(--color-ink) px-6 py-4 text-base font-medium text-(--color-paper) transition active:scale-[0.98]"
            onclick={() => rate(true)}
          >
            Know
          </button>
        </div>
      {/if}
    </footer>
  {:else}
    <p class="m-auto text-sm text-(--color-muted)">No cards available.</p>
  {/if}
</main>
