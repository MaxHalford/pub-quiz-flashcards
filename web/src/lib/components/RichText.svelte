<script lang="ts">
  import type { EntitySpan } from '$lib/types';
  import { renderWithLinks } from '$lib/entities';

  let {
    text,
    spans,
    linkable = true
  }: { text: string; spans?: EntitySpan[]; linkable?: boolean } = $props();
  const parts = $derived(renderWithLinks(text, spans));
</script>

{#each parts as part, i (i)}{#if part.kind === 'link'}<a
      href={part.url}
      target="_blank"
      rel="noopener"
      data-linkable={linkable}
      tabindex={linkable ? 0 : -1}
      class="entity-link"
    >{part.text}</a>{:else}{part.text}{/if}{/each}

<style>
  /* Underline is declared on every state so the line-box height stays
     constant between linkable=true and linkable=false. We only toggle the
     decoration color (and pointer behaviour) — never add/remove the
     decoration itself, which would otherwise cause a sub-pixel layout
     shift when the answer is revealed. */
  .entity-link {
    text-decoration: underline;
    text-decoration-thickness: 1px;
    text-underline-offset: 0.22em;
    color: inherit;
    transition: text-decoration-color 150ms;
  }
  .entity-link[data-linkable='true'] {
    text-decoration-color: color-mix(in srgb, var(--color-accent) 60%, transparent);
    cursor: pointer;
  }
  .entity-link[data-linkable='true']:hover {
    text-decoration-color: var(--color-accent);
  }
  .entity-link[data-linkable='false'] {
    text-decoration-color: transparent;
    cursor: text;
    pointer-events: none;
  }
</style>
