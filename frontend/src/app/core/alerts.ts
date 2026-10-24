import { Injectable, signal } from '@angular/core';

export type AlertKind = 'success' | 'error' | 'info';

export interface AlertAction {
  label: string;
  run: () => void;
}

export interface Alert {
  id: number;
  kind: AlertKind;
  title: string;
  message?: string;
  actions: AlertAction[];
  /** Milliseconds before it hides itself; null keeps it until dismissed. */
  timeout: number | null;
}

export interface AlertInput {
  title: string;
  message?: string;
  actions?: AlertAction[];
  timeout?: number | null;
}

const MAX_ALERTS = 5;
// Errors stay until dismissed so nobody misses them; confirmations clear themselves.
const DEFAULT_TIMEOUT: Record<AlertKind, number | null> = { success: 6000, info: 9000, error: null };

/** The dismissible alert stack shown in the corner of every page. */
@Injectable({ providedIn: 'root' })
export class Alerts {
  readonly items = signal<Alert[]>([]);
  private nextId = 1;

  success(title: string, message?: string): number {
    return this.show('success', { title, message });
  }

  error(title: string, message?: string): number {
    return this.show('error', { title, message });
  }

  info(input: AlertInput): number {
    return this.show('info', input);
  }

  show(kind: AlertKind, input: AlertInput): number {
    const alert: Alert = {
      id: this.nextId++,
      kind,
      title: input.title,
      message: input.message,
      actions: input.actions ?? [],
      timeout: input.timeout === undefined ? DEFAULT_TIMEOUT[kind] : input.timeout,
    };
    // Newest on top; the oldest drops off when the stack is full.
    this.items.update((list) => [alert, ...list].slice(0, MAX_ALERTS));
    return alert.id;
  }

  dismiss(id: number): void {
    this.items.update((list) => list.filter((a) => a.id !== id));
  }

  clear(): void {
    this.items.set([]);
  }
}
