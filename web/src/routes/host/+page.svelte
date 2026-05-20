<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';
  import QRCode from 'qrcode';
  import { loadCards } from '$lib/cards';
  import RichText from '$lib/components/RichText.svelte';
  import SourceRow from '$lib/components/SourceRow.svelte';
  import {
    HostController,
    QUESTION_DURATION_MS
  } from '$lib/game/host.svelte';
  import type { Card } from '$lib/types';

  let cards = $state<Card[]>([]);
  let sources = $state<string[]>([]);
  let selectedSources = $state<Record<string, boolean>>({});
  let loading = $state(true);
  let loadErr = $state<string | null>(null);
  let isDesktop = $state(true);

  let controller = $state<HostController | null>(null);
  let qrDataUrl = $state<string | null>(null);
  let now = $state(Date.now());
  let nowTimer: ReturnType<typeof setInterval> | null = null;

  onMount(async () => {
    isDesktop =
      window.matchMedia('(min-width: 768px) and (pointer: fine)').matches;
    try {
      const { cards: allCards } = await loadCards();
      cards = allCards;
      sources = [...new Set(allCards.map((c) => c.source))].sort();
      for (const s of sources) selectedSources[s] = true;
    } catch (e) {
      loadErr = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
    nowTimer = setInterval(() => (now = Date.now()), 100);
  });

  onDestroy(() => {
    if (nowTimer !== null) clearInterval(nowTimer);
    controller?.destroy();
  });

  const filteredCards = $derived(
    cards.filter((c) => selectedSources[c.source])
  );
  const canStartSession = $derived(filteredCards.length >= 4);

  const joinUrl = $derived.by(() => {
    if (!controller?.peerId) return null;
    return `${window.location.origin}${base}/play?room=${controller.peerId}`;
  });

  $effect(() => {
    const url = joinUrl;
    if (!url) {
      qrDataUrl = null;
      return;
    }
    QRCode.toDataURL(url, { margin: 1, scale: 8 }).then((d) => {
      qrDataUrl = d;
    });
  });

  const connectedPlayers = $derived(
    controller?.players.filter((p) => p.connected) ?? []
  );

  const remainingMs = $derived(
    controller?.mode === 'question'
      ? Math.max(0, controller.questionDeadline - now)
      : controller?.mode === 'paused'
        ? 0
        : 0
  );
  const remainingPct = $derived((remainingMs / QUESTION_DURATION_MS) * 100);

  const isPlaying = $derived(
    controller !== null &&
      (controller.mode === 'question' ||
        controller.mode === 'reveal' ||
        controller.mode === 'paused')
  );

  function startSession() {
    const c = new HostController(filteredCards);
    controller = c;
    c.init();
  }

  function togglePause() {
    if (!controller) return;
    if (controller.mode === 'paused') controller.resume();
    else controller.pause();
  }

  function endSession(opts: { confirm?: boolean } = {}) {
    if (opts.confirm) {
      const n = connectedPlayers.length;
      const msg =
        n > 0
          ? `End the session and disconnect ${n} player${n === 1 ? '' : 's'}?`
          : 'End the session?';
      if (!window.confirm(msg)) return;
    }
    controller?.destroy();
    controller = null;
    qrDataUrl = null;
  }

  function copyJoinUrl() {
    if (joinUrl) navigator.clipboard?.writeText(joinUrl);
  }
</script>

<svelte:head>
  <title>Host a quiz · Pub quiz</title>
</svelte:head>

<main class="min-h-[100dvh]">
  {#if !isPlaying}
    <div class="mx-auto flex min-h-[100dvh] max-w-md flex-col px-6 pt-safe-10 pb-safe-10">
      <header class="flex items-center justify-between">
        <a class="text-sm text-(--color-muted) hover:text-(--color-ink)" href="{base}/">← Back</a>
        <h1 class="font-serif text-lg">Host a quiz</h1>
        <span class="w-12"></span>
      </header>

      {#if !isDesktop}
        <section class="mt-10 text-center">
          <h2 class="font-serif text-xl">Needs a laptop</h2>
          <p class="mt-2 text-sm text-(--color-muted)">
            Quiz sessions are hosted on a larger screen. Open this page on a
            desktop or laptop browser.
          </p>
        </section>
      {:else if loading}
        <p class="mt-20 text-center text-sm text-(--color-muted)">Loading…</p>
      {:else if loadErr}
        <p class="mt-20 text-center text-sm text-(--color-accent)">Failed: {loadErr}</p>
      {:else if !controller}
        <section class="mt-10 space-y-6">
          <div>
            <h2 class="font-serif text-xl">Question sources</h2>
            <p class="mt-1 text-sm text-(--color-muted)">
              Pick at least one. Questions run continuously until you end the
              session.
            </p>
            <div class="mt-4 space-y-2">
              {#each sources as src (src)}
                {@const count = cards.filter((c) => c.source === src).length}
                <SourceRow
                  source={src}
                  {count}
                  checked={selectedSources[src]}
                  onchange={(c) => (selectedSources[src] = c)}
                />
              {/each}
            </div>
          </div>

          <button
            class="w-full rounded-2xl bg-(--color-ink) px-6 py-3 text-sm font-medium text-(--color-paper) transition active:scale-[0.98] disabled:opacity-40"
            disabled={!canStartSession}
            onclick={startSession}
          >
            {canStartSession ? 'Start session' : 'Need at least 4 cards'}
          </button>
        </section>
      {:else if controller.error}
        <section class="mt-10 text-center">
          <h2 class="font-serif text-xl text-(--color-accent)">Session failed</h2>
          <p class="mt-2 text-sm text-(--color-muted)">{controller.error}</p>
          <button class="mt-6 text-sm underline" onclick={() => endSession()}>Back</button>
        </section>
      {:else if controller.mode === 'connecting'}
        <p class="mt-20 text-center text-sm text-(--color-muted)">
          Connecting to the broker…
        </p>
      {/if}
    </div>
  {/if}

  {#if isPlaying && controller?.currentQuestion}
    {@const q = controller.currentQuestion}
    {@const paused = controller.mode === 'paused'}
    {@const revealing = controller.mode === 'reveal'}
    <div class="mx-auto grid max-w-7xl gap-10 px-8 py-8 lg:grid-cols-[1fr_320px]">
      <!-- Main game area -->
      <div class="flex min-h-[calc(100dvh-4rem)] flex-col">
        <header class="flex items-center justify-between text-sm text-(--color-muted)">
          <span>Question {controller.questionIndex}</span>
          <span class="flex items-center gap-4">
            {#if controller.mode === 'question'}
              <span>{Math.ceil(remainingMs / 1000)}s</span>
            {:else if revealing}
              <span>Revealing…</span>
            {/if}
            <button
              class="rounded-full border border-(--color-muted)/30 px-3 py-1 text-xs hover:bg-(--color-paper-dim)"
              onclick={togglePause}
            >
              {paused ? 'Resume' : 'Pause'}
            </button>
            <button
              class="rounded-full border border-(--color-muted)/30 px-3 py-1 text-xs hover:bg-(--color-paper-dim)"
              onclick={() => endSession({ confirm: true })}
            >
              End
            </button>
          </span>
        </header>
        <div class="mt-2 h-1 w-full overflow-hidden rounded-full bg-(--color-paper-dim)">
          <div
            class="h-full bg-(--color-ink) transition-[width] duration-100 ease-linear"
            style:width="{controller.mode === 'question' ? remainingPct : revealing ? 0 : remainingPct}%"
          ></div>
        </div>

        <section
          class="mt-10 mb-8 flex flex-1 items-center transition-opacity"
          class:opacity-40={paused}
        >
          <p class="font-serif text-4xl leading-tight lg:text-5xl">
            <RichText text={q.q} />
          </p>
        </section>

        <div class="grid grid-cols-2 gap-4 pb-4 transition-opacity" class:opacity-40={paused}>
          {#each q.choices as choice, i (i)}
            {@const tally = controller.players.filter(
              (p) => p.connected && p.lastChoiceIndex === i
            ).length}
            {@const isCorrect = revealing && i === q.correctIndex}
            <div
              class="flex items-center justify-between rounded-2xl border-2 px-6 py-5 text-xl transition-colors {isCorrect
                ? 'border-green-600 bg-green-100 dark:bg-green-900'
                : 'border-(--color-muted)/20 bg-(--color-paper-dim)'} {revealing && !isCorrect ? 'opacity-50' : ''}"
            >
              <span class="flex items-center gap-4">
                <span class="font-mono text-sm text-(--color-muted)">{String.fromCharCode(65 + i)}</span>
                <RichText text={choice} />
              </span>
              {#if tally > 0}
                <span class="text-sm text-(--color-muted)">{tally}</span>
              {/if}
            </div>
          {/each}
        </div>

        {#if paused}
          <div class="pointer-events-none fixed inset-0 flex items-center justify-center">
            <div class="rounded-3xl bg-(--color-ink)/90 px-12 py-8 text-center text-(--color-paper) shadow-2xl">
              <p class="font-serif text-4xl">Paused</p>
            </div>
          </div>
        {/if}
      </div>

      <!-- Side panel: QR + scoreboard -->
      <aside class="flex flex-col gap-6">
        <div class="rounded-2xl border border-(--color-muted)/20 p-4">
          <p class="text-xs tracking-wider text-(--color-muted) uppercase">Join</p>
          {#if qrDataUrl}
            <img src={qrDataUrl} alt="Join QR code" class="mt-2 w-full rounded-xl bg-white p-2" />
          {/if}
          {#if joinUrl}
            <div class="mt-2 flex items-center gap-2 text-xs text-(--color-muted)">
              <code class="truncate flex-1 rounded bg-(--color-paper-dim) px-2 py-1 font-mono">{joinUrl}</code>
              <button class="shrink-0 underline" onclick={copyJoinUrl}>copy</button>
            </div>
          {/if}
        </div>

        <div class="rounded-2xl border border-(--color-muted)/20 p-4">
          <p class="text-xs tracking-wider text-(--color-muted) uppercase">
            Players ({connectedPlayers.length})
          </p>
          <ul class="mt-3 space-y-1.5 text-sm">
            {#each controller.snapshotScores() as s (s.id)}
              <li
                class="flex items-center justify-between rounded-lg px-3 py-2"
                class:bg-(--color-paper-dim)={s.connected}
                class:opacity-40={!s.connected}
              >
                <span class="flex items-center gap-2 truncate">
                  <span
                    class="h-1.5 w-1.5 rounded-full"
                    class:bg-(--color-ink)={s.connected}
                    class:bg-(--color-muted)={!s.connected}
                  ></span>
                  <span class="truncate">{s.username}</span>
                </span>
                <span class="font-mono">{s.score}</span>
              </li>
            {:else}
              <li class="text-xs text-(--color-muted)">No one yet — scan the QR</li>
            {/each}
          </ul>
        </div>
      </aside>
    </div>
  {/if}
</main>
