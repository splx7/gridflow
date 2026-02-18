"use client";

import { useEffect } from "react";

interface ShortcutHandlers {
  onSave?: () => void;
  onRun?: () => void;
}

export function useKeyboardShortcuts({ onSave, onRun }: ShortcutHandlers) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;

      // Cmd/Ctrl+S — Save
      if (mod && e.key === "s") {
        e.preventDefault();
        onSave?.();
      }

      // Cmd/Ctrl+Enter — Run simulation
      if (mod && e.key === "Enter") {
        e.preventDefault();
        onRun?.();
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onSave, onRun]);
}
