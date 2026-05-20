<script lang="ts">
  import Tooltip from './Tooltip.svelte';

  let { count }: { count: number } = $props();
</script>

<button
  type="button"
  class="group relative inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-semibold {count > 0
    ? 'bg-(--color-accent)/15 text-(--color-accent)'
    : 'bg-(--color-muted)/15 text-(--color-muted)'}"
>
  <svg viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true">
    <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5Z" />
  </svg>
  <span class="tabular-nums">{count}</span>
  <Tooltip text="{count} day{count === 1 ? '' : 's'} in a row" placement="bottom-start" />
</button>
