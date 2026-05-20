<script lang="ts">
  import { sourceLabel, sourceFlag } from '$lib/cards';

  type Props = {
    source: string;
    count: number;
    checked: boolean;
    disabled?: boolean;
    onchange: (checked: boolean) => void;
  };
  let { source, count, checked, disabled = false, onchange }: Props = $props();
</script>

<label class="flex items-center gap-3 rounded-xl border border-(--color-muted)/20 px-4 py-3 text-sm">
  <input
    type="checkbox"
    {checked}
    {disabled}
    onchange={(e) => onchange((e.currentTarget as HTMLInputElement).checked)}
    class="h-4 w-4 accent-(--color-ink) disabled:opacity-50"
  />
  <span class="flex-1">
    <span aria-hidden="true">{sourceFlag(source)}</span>
    {sourceLabel(source)}
  </span>
  <span class="text-xs text-(--color-muted)">{count} cards</span>
</label>
