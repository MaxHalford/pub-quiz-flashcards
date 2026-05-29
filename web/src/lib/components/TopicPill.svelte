<script lang="ts">
  type Props = {
    label: string;
    count: number;
    enabled: boolean;
    onToggle: (enabled: boolean) => void;
  };
  let { label, count, enabled, onToggle }: Props = $props();

  function abbrev(n: number): string {
    if (n < 1000) return String(n);
    const k = n / 1000;
    return k >= 10 ? `${Math.round(k)}k` : `${k.toFixed(1)}k`;
  }
</script>

<button
  type="button"
  class={[
    'rounded-full border px-3 py-1.5 text-sm transition active:scale-95',
    enabled
      ? 'bg-(--color-ink) text-(--color-paper) border-transparent'
      : 'border-(--color-muted)/40 text-(--color-muted)'
  ]}
  aria-pressed={enabled}
  aria-label={`${enabled ? 'Hide' : 'Show'} ${label} questions`}
  onclick={() => onToggle(!enabled)}
>
  {label}
  <span class="ml-1 text-xs opacity-70">{abbrev(count)}</span>
</button>
