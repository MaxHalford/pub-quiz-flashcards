<script lang="ts">
  import { base } from '$app/paths';
  import { exportBackup, importBackup } from '$lib/backup';
  import { loadState } from '$lib/storage';

  let message = $state<{ kind: 'ok' | 'err'; text: string } | null>(null);
  let fileInput: HTMLInputElement;

  let cardCount = $state(0);
  let deviceId = $state('');
  $effect(() => {
    const s = loadState();
    cardCount = Object.keys(s.cards).length;
    deviceId = s.deviceId;
  });

  function onExport() {
    try {
      exportBackup();
      message = { kind: 'ok', text: 'Backup downloaded.' };
    } catch (e) {
      message = { kind: 'err', text: e instanceof Error ? e.message : String(e) };
    }
  }

  async function onImportFile(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    const text = await file.text();
    const result = importBackup(text);
    if (result.ok) {
      message = { kind: 'ok', text: 'Backup imported. Reloading…' };
      setTimeout(() => location.reload(), 600);
    } else {
      message = { kind: 'err', text: `Import failed: ${result.reason}` };
    }
  }
</script>

<main class="mx-auto flex min-h-[100dvh] max-w-md flex-col px-6 py-10">
  <header class="flex items-center justify-between">
    <a class="text-sm text-(--color-muted) hover:text-(--color-ink)" href="{base}/">← Back</a>
    <h1 class="font-serif text-lg">Settings</h1>
    <span class="w-12"></span>
  </header>

  <section class="mt-10 space-y-6">
    <div>
      <h2 class="font-serif text-xl">Backup</h2>
      <p class="mt-1 text-sm text-(--color-muted)">
        Your progress is saved only in this browser. Export occasionally and keep the file somewhere safe.
      </p>
      <div class="mt-4 flex flex-col gap-2">
        <button
          class="rounded-2xl bg-(--color-ink) px-6 py-3 text-sm font-medium text-(--color-paper) transition active:scale-[0.98]"
          onclick={onExport}
        >
          Export backup
        </button>
        <button
          class="rounded-2xl border border-(--color-muted)/30 px-6 py-3 text-sm font-medium transition active:scale-[0.98]"
          onclick={() => fileInput.click()}
        >
          Import backup
        </button>
        <input
          bind:this={fileInput}
          type="file"
          accept="application/json,.json"
          class="hidden"
          onchange={onImportFile}
        />
      </div>
      {#if message}
        <p class="mt-3 text-sm" class:text-green-700={message.kind === 'ok'} class:text-(--color-accent)={message.kind === 'err'}>
          {message.text}
        </p>
      {/if}
    </div>

    <div class="border-t border-(--color-muted)/20 pt-6 text-xs text-(--color-muted)">
      <p>Cards reviewed: {cardCount}</p>
      <p class="mt-1 font-mono">Device: {deviceId.slice(0, 8)}…</p>
    </div>
  </section>
</main>
