<script lang="ts">
  import { heatmapCells } from '$lib/streak';
  import Tooltip from './Tooltip.svelte';

  let { history, weeks = 12 }: { history: Record<string, number>; weeks?: number } = $props();

  const cols = $derived(heatmapCells(history, weeks));

  function level(count: number): number {
    if (count === 0) return 0;
    if (count <= 3) return 1;
    if (count <= 9) return 2;
    return 3;
  }

  function tooltipFor(date: string, count: number): string {
    const [y, m, d] = date.split('-').map(Number);
    const formatted = new Date(y, m - 1, d).toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    });
    if (count === 0) return `${formatted} · no activity`;
    return `${formatted} · ${count} answered`;
  }
</script>

<div class="inline-grid grid-flow-col grid-rows-7 gap-1" role="img" aria-label="Activity heatmap">
  {#each cols as col (col[0].date)}
    {#each col as cell (cell.date)}
      {#if cell.isFuture}
        <div class="h-3 w-3"></div>
      {:else}
        {@const lvl = level(cell.count)}
        <div class="group relative h-3 w-3">
          <div
            class="h-full w-full rounded-[3px]"
            class:bg-l0={lvl === 0}
            class:bg-l1={lvl === 1}
            class:bg-l2={lvl === 2}
            class:bg-l3={lvl === 3}
          ></div>
          <Tooltip text={tooltipFor(cell.date, cell.count)} placement="top-center" />
        </div>
      {/if}
    {/each}
  {/each}
</div>

<style>
  .bg-l0 {
    background: color-mix(in srgb, var(--color-muted) 12%, transparent);
  }
  .bg-l1 {
    background: color-mix(in srgb, var(--color-accent) 35%, transparent);
  }
  .bg-l2 {
    background: color-mix(in srgb, var(--color-accent) 65%, transparent);
  }
  .bg-l3 {
    background: var(--color-accent);
  }
</style>
