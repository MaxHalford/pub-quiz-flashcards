import type { Action } from 'svelte/action';

type Params = {
  onLeft: () => void;
  onRight: () => void;
  enabled: () => boolean;
};

const THRESHOLD = 80;
const VERTICAL_TOLERANCE = 80;

export const swipe: Action<HTMLElement, Params> = (node, initial) => {
  let params = initial;
  let startX = 0;
  let startY = 0;
  let isDown = false;

  function reset() {
    isDown = false;
    node.style.transition = 'transform 200ms ease-out';
    node.style.transform = '';
  }

  function onDown(e: PointerEvent) {
    if (!params.enabled()) return;
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    isDown = true;
    startX = e.clientX;
    startY = e.clientY;
    node.style.transition = 'none';
    try {
      node.setPointerCapture(e.pointerId);
    } catch {
      /* not all browsers support capture */
    }
  }

  function onMove(e: PointerEvent) {
    if (!isDown) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    if (Math.abs(dy) > Math.abs(dx) * 2) return;
    const rotation = dx * 0.04;
    node.style.transform = `translateX(${dx}px) rotate(${rotation}deg)`;
  }

  function onUp(e: PointerEvent) {
    if (!isDown) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    reset();
    if (Math.abs(dx) >= THRESHOLD && Math.abs(dy) <= VERTICAL_TOLERANCE) {
      if (dx > 0) params.onRight();
      else params.onLeft();
    }
  }

  node.style.touchAction = 'pan-y';
  node.addEventListener('pointerdown', onDown);
  node.addEventListener('pointermove', onMove);
  node.addEventListener('pointerup', onUp);
  node.addEventListener('pointercancel', reset);

  return {
    update(next: Params) {
      params = next;
    },
    destroy() {
      node.removeEventListener('pointerdown', onDown);
      node.removeEventListener('pointermove', onMove);
      node.removeEventListener('pointerup', onUp);
      node.removeEventListener('pointercancel', reset);
    }
  };
};
