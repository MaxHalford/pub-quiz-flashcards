<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';
  import { page } from '$app/state';
  import RichText from '$lib/components/RichText.svelte';
  import { PlayerController, type PlayerMode } from '$lib/game/player.svelte';
  import { MAX_USERNAME_LEN } from '$lib/game/host.svelte';

  let roomId = $state<string | null>(null);
  let controller = $state<PlayerController | null>(null);
  let usernameInput = $state('');
  let now = $state(Date.now());
  let nowTimer: ReturnType<typeof setInterval> | null = null;
  let questionStartedAt = $state(0);
  let questionStartDuration = $state(0);

  onMount(() => {
    roomId = page.url.searchParams.get('room');
    if (!roomId) return;
    const c = new PlayerController(roomId);
    controller = c;
    c.init();
    nowTimer = setInterval(() => (now = Date.now()), 100);
  });

  onDestroy(() => {
    if (nowTimer !== null) clearInterval(nowTimer);
    controller?.destroy();
  });

  // Whenever the currentQuestion identity changes (new question OR refreshed durationMs on resume),
  // reset the local countdown anchor.
  $effect(() => {
    if (controller?.currentQuestion) {
      questionStartedAt = Date.now();
      questionStartDuration = controller.currentQuestion.durationMs;
    }
  });

  const mode = $derived<PlayerMode>(controller?.mode ?? 'connecting');
  const paused = $derived(controller?.paused ?? false);

  const remainingMs = $derived.by(() => {
    if (!controller?.currentQuestion || mode !== 'question') return 0;
    if (paused) return controller.pausedRemainingMs ?? 0;
    const elapsed = now - questionStartedAt;
    return Math.max(0, questionStartDuration - elapsed);
  });
  const remainingPct = $derived(
    questionStartDuration > 0 ? (remainingMs / questionStartDuration) * 100 : 0
  );

  function submitJoin(e: Event) {
    e.preventDefault();
    const name = usernameInput.trim().slice(0, MAX_USERNAME_LEN);
    if (!name || !controller) return;
    controller.submitJoin(name);
  }

  function pick(i: number) {
    controller?.submitAnswer(i);
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
      navigator.vibrate(10);
    }
  }

  const myReveal = $derived(controller?.lastReveal ?? null);
  const myScore = $derived.by(() => {
    const c = controller;
    if (!c?.lastReveal) return 0;
    const me = c.lastReveal.scores.find((s) => s.username === c.username);
    return me?.score ?? 0;
  });
  const myRank = $derived.by(() => {
    const c = controller;
    if (!c?.lastReveal) return null;
    const idx = c.lastReveal.scores.findIndex((s) => s.username === c.username);
    return idx >= 0 ? idx + 1 : null;
  });

  const choiceColors = ['#b85c38', '#1f6b46', '#3b6ea5', '#7a4d8f'];
</script>

<svelte:head>
  <title>Play · Pub quiz</title>
</svelte:head>

<main class="relative mx-auto flex min-h-[100dvh] max-w-md flex-col px-6 pt-safe-6 pb-safe-6">
  {#if !roomId}
    <div class="m-auto text-center">
      <h1 class="font-serif text-2xl">No room</h1>
      <p class="mt-4 text-sm text-(--color-muted)">
        Scan the QR code on the host screen to join.
      </p>
      <a href="{base}/" class="mt-6 inline-block text-sm underline">← Back</a>
    </div>
  {:else if mode === 'connecting'}
    <p class="m-auto text-sm text-(--color-muted)">Connecting…</p>
  {:else if mode === 'joining'}
    <form class="m-auto w-full" onsubmit={submitJoin}>
      <h1 class="font-serif text-3xl tracking-tight">Pick a name</h1>
      <!-- svelte-ignore a11y_autofocus -->
      <input
        type="text"
        bind:value={usernameInput}
        maxlength={MAX_USERNAME_LEN}
        autofocus
        placeholder="e.g. Sam"
        class="mt-8 w-full rounded-2xl border-2 border-(--color-muted)/30 bg-transparent px-5 py-4 text-xl outline-none focus:border-(--color-ink)"
      />
      <button
        type="submit"
        class="mt-4 w-full rounded-2xl bg-(--color-ink) px-6 py-4 text-base font-medium text-(--color-paper) disabled:opacity-40"
        disabled={!usernameInput.trim()}
      >
        Join
      </button>
    </form>
  {:else if mode === 'waiting'}
    <div class="m-auto text-center">
      <h1 class="font-serif text-3xl tracking-tight">You're in</h1>
      <p class="mt-2 text-sm text-(--color-muted)">@{controller?.username}</p>
      <div class="mt-12">
        <div class="mx-auto h-2 w-2 animate-pulse rounded-full bg-(--color-ink)"></div>
        <p class="mt-6 text-sm text-(--color-muted)">
          Waiting for the next question…
        </p>
      </div>
    </div>
  {:else if mode === 'question' && controller?.currentQuestion}
    {@const q = controller.currentQuestion}
    <header class="flex items-center justify-between text-xs text-(--color-muted)">
      <span>Question {q.index}</span>
      <span>{Math.ceil(remainingMs / 1000)}s</span>
    </header>
    <div class="mt-2 h-1 w-full overflow-hidden rounded-full bg-(--color-paper-dim)">
      <div
        class="h-full bg-(--color-ink) transition-[width] duration-100 ease-linear"
        style:width="{remainingPct}%"
      ></div>
    </div>

    {#if controller.myChoice === null}
      <section class="mt-8 flex-1">
        <p class="font-serif text-xl leading-snug">
          <RichText text={q.q} />
        </p>
      </section>
      <div class="mt-6 grid grid-cols-1 gap-3 pb-2">
        {#each q.choices as choice, i (i)}
          <button
            class="rounded-2xl px-5 py-5 text-left text-base font-medium text-white transition active:scale-[0.98] disabled:opacity-50"
            style:background-color={choiceColors[i]}
            onclick={() => pick(i)}
            disabled={paused}
          >
            <span class="mr-3 font-mono text-sm opacity-70">{String.fromCharCode(65 + i)}</span>
            {choice}
          </button>
        {/each}
      </div>
    {:else}
      <div class="m-auto text-center">
        <p class="font-serif text-2xl">Answer locked</p>
        <p class="mt-3 text-sm text-(--color-muted)">
          You picked <span class="font-mono">{String.fromCharCode(65 + controller.myChoice)}</span>. Waiting for others…
        </p>
      </div>
    {/if}
  {:else if mode === 'reveal' && myReveal && controller?.currentQuestion}
    {@const q = controller.currentQuestion}
    {@const myChoice = controller.myChoice}
    {@const correct = myChoice !== null && myChoice === myReveal.correctIndex}
    <div class="m-auto w-full text-center">
      <p
        class="font-serif text-5xl tracking-tight"
        class:text-(--color-accent)={!correct}
      >
        {correct ? 'Correct' : myChoice === null ? '—' : 'Wrong'}
      </p>
      <p class="mt-4 text-sm text-(--color-muted)">
        Answer: <span class="text-(--color-ink)">{q.choices[myReveal.correctIndex]}</span>
      </p>
      {#if correct}
        <p class="mt-3 text-lg text-(--color-muted)">+{myReveal.yourPoints}</p>
      {/if}
      <div class="mt-12">
        <p class="text-xs tracking-wider text-(--color-muted) uppercase">Total</p>
        <p class="mt-1 font-mono text-3xl">{myScore}</p>
        {#if myRank !== null}
          <p class="mt-2 text-sm text-(--color-muted)">
            Rank {myRank} of {myReveal.scores.length}
          </p>
        {/if}
      </div>
    </div>
  {:else if mode === 'kicked'}
    <div class="m-auto text-center">
      <p class="font-serif text-2xl text-(--color-accent)">{controller?.errorMsg ?? 'Rejected'}</p>
      <a href="{base}/" class="mt-6 inline-block text-sm underline">← Back</a>
    </div>
  {:else if mode === 'error'}
    <div class="m-auto text-center">
      <p class="font-serif text-2xl text-(--color-accent)">
        {controller?.errorMsg ?? 'Something went wrong'}
      </p>
      <a href="{base}/" class="mt-6 inline-block text-sm underline">← Back</a>
    </div>
  {/if}

  {#if paused}
    <div class="pointer-events-none fixed inset-0 flex items-center justify-center bg-(--color-ink)/40 backdrop-blur-sm">
      <div class="rounded-2xl bg-(--color-paper) px-8 py-5 text-center shadow-xl">
        <p class="font-serif text-2xl">Paused</p>
      </div>
    </div>
  {/if}
</main>
