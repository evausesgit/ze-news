"use client";

import { useRef } from "react";

// Double-clic ET double-tap mobile avec un seul mécanisme : l'événement natif
// `dblclick` n'est pas fiable au toucher (iOS). Deux relâchements à moins de
// 320 ms et à moins de 24 px l'un de l'autre = double tap. Appelé pendant le
// geste utilisateur, donc window.open n'est pas bloqué.
export function useDoubleTap(onDoubleTap: () => void) {
  const last = useRef<{ t: number; x: number; y: number } | null>(null);
  return (e: React.PointerEvent) => {
    const now = e.timeStamp;
    const prev = last.current;
    if (prev && now - prev.t < 320 && Math.hypot(e.clientX - prev.x, e.clientY - prev.y) < 24) {
      last.current = null;
      onDoubleTap();
      return true;
    }
    last.current = { t: now, x: e.clientX, y: e.clientY };
    return false;
  };
}
