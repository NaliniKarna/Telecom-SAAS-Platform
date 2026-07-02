import { Injectable, signal } from '@angular/core';

export type ThemeMode = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'telecom-theme';

/**
 * Controls light/dark appearance by setting `color-scheme` on the document
 * root. Material's tokens (set up via mat.theme with `color-scheme: light dark`)
 * follow this automatically, so no palette swap is needed. The choice is
 * persisted; 'system' defers to the OS preference.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly mode = signal<ThemeMode>('system');

  constructor() {
    const saved = this.read();
    this.set(saved ?? 'system');
  }

  /** Cycle through light -> dark -> system for a single toggle button. */
  cycle(): void {
    const next: Record<ThemeMode, ThemeMode> = {
      light: 'dark',
      dark: 'system',
      system: 'light',
    };
    this.set(next[this.mode()]);
  }

  set(mode: ThemeMode): void {
    this.mode.set(mode);
    const root = document.documentElement;
    // 'system' -> let the OS decide (both keywords); otherwise force one.
    root.style.colorScheme = mode === 'system' ? 'light dark' : mode;
    this.write(mode);
  }

  /** Material icon name reflecting the current mode. */
  icon(): string {
    switch (this.mode()) {
      case 'light':
        return 'light_mode';
      case 'dark':
        return 'dark_mode';
      default:
        return 'brightness_auto';
    }
  }

  label(): string {
    switch (this.mode()) {
      case 'light':
        return 'Light mode';
      case 'dark':
        return 'Dark mode';
      default:
        return 'System theme';
    }
  }

  private read(): ThemeMode | null {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      return v === 'light' || v === 'dark' || v === 'system' ? v : null;
    } catch {
      return null;
    }
  }

  private write(mode: ThemeMode): void {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      /* storage unavailable — non-fatal */
    }
  }
}
