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
  import Tooltip from '$lib/components/Tooltip.svelte';
  import Onboarding from '$lib/components/Onboarding.svelte';
  import type { Card, AppState, CardRating, SessionEntity } from '$lib/types';

  let cardIndex = $state<Map<string, Card>>(new Map());
  let sourceCounts = $state<Array<{ source: string; count: number }>>([]);
  let appState = $state<AppState | null>(null);
  let revealed = $state(false);
  let error = $state<string | null>(null);
  let loading = $state(true);
  let canHost = $state(false);

  const needsOnboarding = $derived(appState !== null && !appState.settings.onboarded);

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

  const groupedEntities = $derived.by(() => {
    const groups: Record<CardRating, SessionEntity[]> = { unknown: [], knew: [], skipped: [] };
    if (!appState) return groups;
    const priority: Record<CardRating, number> = { skipped: 0, knew: 1, unknown: 2 };
    const seen = new Map<string, { entity: SessionEntity; rating: CardRating }>();
    for (const r of appState.daily.results) {
      const card = cardIndex.get(r.id);
      if (!card) continue;
      for (const span of [...(card.q_entities ?? []), ...(card.a_entities ?? [])]) {
        const existing = seen.get(span.title);
        if (!existing || priority[r.rating] > priority[existing.rating]) {
          seen.set(span.title, {
            entity: { title: span.title, url: span.url },
            rating: r.rating
          });
        }
      }
    }
    for (const { entity, rating } of seen.values()) {
      groups[rating].push(entity);
    }
    return groups;
  });
  const hasEntities = $derived(
    groupedEntities.unknown.length + groupedEntities.knew.length + groupedEntities.skipped.length >
      0
  );

  onMount(async () => {
    canHost = window.matchMedia('(min-width: 768px) and (pointer: fine)').matches;
    try {
      const { cards } = await loadCards();
      cardIndex = new Map(cards.map((c) => [c.id, c]));
      const counts = new Map<string, number>();
      for (const c of cards) counts.set(c.source, (counts.get(c.source) ?? 0) + 1);
      sourceCounts = [...counts.entries()]
        .map(([source, count]) => ({ source, count }))
        .sort((a, b) => sourceLabel(a.source).localeCompare(sourceLabel(b.source)));
      const state = ensureToday(loadState());
      state.daily.queue = state.daily.queue.filter((id) => cardIndex.has(id));
      if (
        state.settings.onboarded &&
        state.daily.queue.length === 0 &&
        state.daily.reviewed < dailyGoalCapFor(state)
      ) {
        state.daily.queue = replan(state);
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

  function replan(s: AppState): string[] {
    const cards = [...cardIndex.values()];
    const seen = new Set(s.daily.results.map((r) => r.id));
    return planSession(cards, s, capRemaining(s), Date.now(), seen).map((c) => c.id);
  }

  function rate(rating: CardRating) {
    if (!appState || !currentCard) return;
    const card = currentCard;
    if (rating === 'skipped') {
      appState.tombstoned[card.id] = true;
    } else {
      appState.cards[card.id] = applyRating(
        appState.cards[card.id],
        rating === 'knew',
        appState.settings.shortTerm
      );
    }
    const today = todayKey();
    appState.history[today] = (appState.history[today] ?? 0) + 1;
    appState.daily.reviewed += 1;
    appState.daily.results.push({ id: card.id, rating });
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
    appState.daily.queue = replan(appState);
    saveState(appState);
  }

  function completeOnboarding(disabledSources: Record<string, true>) {
    if (!appState) return;
    appState.settings.disabledSources = disabledSources;
    appState.settings.onboarded = true;
    appState.daily.queue = replan(appState);
    saveState(appState);
  }
</script>

{#if needsOnboarding && appState}
  <Onboarding {sourceCounts} onConfirm={completeOnboarding} />
{:else}
<main class="mx-auto flex min-h-[100dvh] max-w-md flex-col px-6 pt-safe-6 pb-safe-6">
  <nav class="flex items-center justify-between">
    <Streak count={streak} />
    <div class="flex items-center gap-1">
      {#if canHost}
        <a
          href="{base}/host"
          class="group relative rounded-full p-2 text-(--color-muted) transition hover:text-(--color-ink)"
          aria-label="Host a quiz"
        >
          <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="6" y1="11" x2="10" y2="11" />
            <line x1="8" y1="9" x2="8" y2="13" />
            <line x1="15" y1="12" x2="15.01" y2="12" />
            <line x1="18" y1="10" x2="18.01" y2="10" />
            <path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258A4 4 0 0 0 17.32 5z" />
          </svg>
          <Tooltip text="Host a quiz" placement="bottom-center" />
        </a>
      {/if}
      <a
        href="{base}/settings"
        class="group relative rounded-full p-2 text-(--color-muted) transition hover:text-(--color-ink)"
        aria-label="Settings"
      >
        <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
        </svg>
        <Tooltip text="Settings" placement="bottom-end" />
      </a>
    </div>
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
        class="group relative mt-12 rounded-full bg-(--color-ink) px-6 py-3 text-sm font-medium text-(--color-paper) transition active:scale-95"
        onclick={keepGoing}
      >
        Keep going (+{appState.settings.dailyGoal})
        <Tooltip
          text="Queue up another {appState.settings.dailyGoal} questions for today"
          placement="bottom-center"
        />
      </button>

      {#if hasEntities}
        <div class="mt-12 space-y-8 text-left">
          {#each [{ key: 'unknown' as const, label: "Didn't know" }, { key: 'knew' as const, label: 'Knew it' }, { key: 'skipped' as const, label: "Don't want to know" }] as group (group.key)}
            {@const items = groupedEntities[group.key]}
            {#if items.length > 0}
              <div>
                <p class="text-xs tracking-wider text-(--color-muted) uppercase">{group.label}</p>
                <ul class="mt-4 space-y-2 text-lg leading-snug">
                  {#each items as e (e.title)}
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
          {/each}
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
            style:background-color={r === undefined || r.rating === 'skipped'
              ? 'transparent'
              : r.rating === 'knew'
                ? 'var(--color-ink)'
                : 'color-mix(in srgb, var(--color-muted) 30%, transparent)'}
            style:border-color={r === undefined || r.rating === 'skipped' ? undefined : 'transparent'}
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
            <div class="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-(--color-muted)">
              <a
                class="underline-offset-4 hover:underline"
                href={currentCard.source_url}
                target="_blank"
                rel="noopener"
                tabindex={revealed ? 0 : -1}
              >
                {sourceLabel(currentCard.source)}, {currentCard.source_date}
              </a>
              {#if currentCard.topic}
                <span
                  class="rounded-full border border-(--color-muted)/30 px-2 py-0.5 tracking-wide"
                  >{currentCard.topic}</span
                >
              {/if}
            </div>
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
            class="group relative rounded-2xl border border-transparent px-6 py-4 text-base font-medium transition active:scale-[0.98]"
            style:background-color="color-mix(in srgb, var(--color-muted) 30%, transparent)"
            onclick={() => rate('unknown')}
          >
            Didn't know
            <Tooltip text="See this card again soon" placement="top-center" />
          </button>
          <button
            class="group relative rounded-2xl border border-transparent bg-(--color-ink) px-6 py-4 text-base font-medium text-(--color-paper) transition active:scale-[0.98]"
            onclick={() => rate('knew')}
          >
            Knew it
            <Tooltip text="Push the next review further out" placement="top-center" />
          </button>
        </div>
        <button
          class="group relative mt-3 w-full rounded-2xl border border-(--color-muted)/30 px-6 py-4 text-base font-medium transition active:scale-[0.98]"
          onclick={() => rate('skipped')}
        >
          Don't want to know
          <Tooltip text="Hide this card permanently" placement="top-center" />
        </button>
      {/if}
    </footer>
  {:else}
    <p class="m-auto text-sm text-(--color-muted)">No cards available.</p>
  {/if}
</main>
{/if}
