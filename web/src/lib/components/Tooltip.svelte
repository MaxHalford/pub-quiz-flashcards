<script lang="ts">
  type Placement =
    | 'bottom-start'
    | 'bottom-center'
    | 'bottom-end'
    | 'top-start'
    | 'top-center'
    | 'top-end';

  let { text, placement = 'bottom-center' }: { text: string; placement?: Placement } = $props();

  const positionClass = $derived.by(() => {
    const [side, align] = placement.split('-');
    const vertical = side === 'bottom' ? 'top-full mt-2' : 'bottom-full mb-2';
    const horizontal =
      align === 'start'
        ? 'left-0'
        : align === 'end'
          ? 'right-0'
          : 'left-1/2 -translate-x-1/2';
    return `${vertical} ${horizontal}`;
  });
</script>

<span
  role="tooltip"
  class="pointer-events-none absolute z-20 whitespace-nowrap rounded-md bg-(--color-ink) px-2.5 py-1.5 text-xs font-medium text-(--color-paper) opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 {positionClass}"
>
  {text}
</span>
