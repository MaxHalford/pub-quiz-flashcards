<script lang="ts">
  let { count }: { count: number } = $props();
</script>

{#if count > 0}
  <span class="group relative inline-flex">
    <button
      type="button"
      class="inline-flex items-center gap-1.5 rounded-full bg-(--color-accent)/15 px-2.5 py-1 text-sm font-semibold text-(--color-accent)"
      aria-describedby="streak-tooltip"
    >
      <svg viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true">
        <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5Z" />
      </svg>
      <span class="tabular-nums">{count}</span>
    </button>
    <span
      id="streak-tooltip"
      role="tooltip"
      class="pointer-events-none absolute top-full left-0 mt-2 whitespace-nowrap rounded-md bg-(--color-ink) px-2.5 py-1.5 text-xs font-medium text-(--color-paper) opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
    >
      {count} day{count === 1 ? '' : 's'} in a row
    </span>
  </span>
{/if}
