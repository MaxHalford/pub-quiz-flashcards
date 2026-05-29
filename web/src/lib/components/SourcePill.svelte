<script lang="ts">
  import { sourceLabel, sourceFlag } from '$lib/cards';

  type Props = {
    source: string;
    count: number;
    enabled: boolean;
    locked?: boolean;
    onToggle: (enabled: boolean) => void;
  };
  let { source, count, enabled, locked = false, onToggle }: Props = $props();

  function abbrev(n: number): string {
    if (n < 1000) return String(n);
    const k = n / 1000;
    return k >= 10 ? `${Math.round(k)}k` : `${k.toFixed(1)}k`;
  }
</script>

<button
  type="button"
  class={[
    'rounded-full border px-4 py-2 text-sm transition active:scale-95',
    enabled
      ? 'bg-(--color-ink) text-(--color-paper) border-transparent'
      : 'border-(--color-muted)/40 text-(--color-muted)',
    locked && 'cursor-not-allowed opacity-60'
  ]}
  disabled={locked}
  aria-pressed={enabled}
  aria-label={`${enabled ? 'Disable' : 'Enable'} ${sourceLabel(source)}`}
  onclick={() => onToggle(!enabled)}
>
  <span aria-hidden="true">{sourceFlag(source)}</span>
  {sourceLabel(source)}
  <span class="ml-1 text-xs opacity-70">{abbrev(count)}</span>
</button>
