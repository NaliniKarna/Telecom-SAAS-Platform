import {
  ChangeDetectionStrategy,
  Component,
  computed,
  signal,
} from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { PublicHeaderComponent } from '../public/public-header.component';
import { PublicFooterComponent } from '../public/public-footer.component';
import { DOC_GROUPS, DOC_TOPICS, DocTopic } from './docs.data';

/**
 * Developer documentation portal: a searchable sidebar of topics + a content
 * pane. Content is defined in docs.data.ts and reflects only APIs that exist in
 * the project. Search filters the sidebar and auto-selects the first match.
 */
@Component({
  selector: 'app-docs',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatIconModule, PublicHeaderComponent, PublicFooterComponent],
  template: `
    <app-public-header />

    <div class="docs">
      <aside class="docs__side">
        <div class="search">
          <mat-icon aria-hidden="true">search</mat-icon>
          <input
            type="search"
            placeholder="Search documentation"
            [value]="query()"
            (input)="onSearch($event)"
            aria-label="Search documentation"
          />
        </div>

        <nav class="toc" aria-label="Documentation">
          @for (group of groups; track group) {
            @if (topicsIn(group).length) {
              <div class="toc__group">{{ group }}</div>
              @for (t of topicsIn(group); track t.id) {
                <button
                  type="button"
                  class="toc__link"
                  [class.is-active]="t.id === activeId()"
                  (click)="select(t.id)"
                >
                  {{ t.title }}
                </button>
              }
            }
          }
          @if (!filtered().length) {
            <p class="toc__empty">No topics match “{{ query() }}”.</p>
          }
        </nav>
      </aside>

      <main class="docs__main">
        @if (active(); as t) {
          <span class="docs__eyebrow">{{ t.group }}</span>
          <h1>{{ t.title }}</h1>
          <div class="prose" [innerHTML]="t.html"></div>
        }
      </main>
    </div>

    <app-public-footer />
  `,
  styles: [
    `
      :host {
        --ink: var(--mat-sys-on-surface);
        --muted: var(--mat-sys-on-surface-variant);
        --primary: var(--mat-sys-primary);
        --bg: var(--mat-sys-surface-container-lowest);
        --soft: var(--mat-sys-surface);
        --tint: var(--mat-sys-surface-container-low);
        --border: var(--mat-sys-outline-variant);
        --font: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
        --mono: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
        color-scheme: light;
        display: block;
        background: var(--bg);
        color: var(--ink);
        font-family: var(--font);
      }
      .docs {
        max-width: 1140px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: 260px 1fr;
        gap: clamp(1.5rem, 4vw, 3rem);
        padding: clamp(1.5rem, 4vw, 2.5rem) clamp(1.1rem, 4vw, 2rem) 3rem;
        align-items: start;
      }
      .docs__side {
        position: sticky;
        top: 84px;
      }
      .search {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 0.5rem 0.7rem;
        background: var(--bg);
        margin-bottom: 1.25rem;
      }
      .search:focus-within {
        border-color: color-mix(in srgb, var(--primary) 55%, var(--border));
      }
      .search mat-icon {
        color: var(--muted);
        font-size: 18px;
        width: 18px;
        height: 18px;
      }
      .search input {
        border: 0;
        outline: 0;
        background: transparent;
        font: inherit;
        font-size: 0.9rem;
        color: var(--ink);
        width: 100%;
      }
      .toc__group {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--muted);
        margin: 1rem 0 0.4rem;
        font-weight: 700;
      }
      .toc__link {
        display: block;
        width: 100%;
        text-align: left;
        background: none;
        border: 0;
        font: inherit;
        font-size: 0.92rem;
        color: var(--muted);
        padding: 0.4rem 0.6rem;
        border-radius: 8px;
        cursor: pointer;
        border-left: 2px solid transparent;
        transition: background 0.15s ease, color 0.15s ease;
      }
      .toc__link:hover {
        background: var(--tint);
        color: var(--ink);
      }
      .toc__link.is-active {
        color: var(--primary);
        background: color-mix(in srgb, var(--primary) 9%, transparent);
        border-left-color: var(--primary);
        font-weight: 600;
      }
      .toc__empty {
        font-size: 0.85rem;
        color: var(--muted);
      }
      .docs__main {
        min-width: 0;
      }
      .docs__eyebrow {
        font-size: 0.72rem;
        font-weight: 650;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: var(--primary);
      }
      h1 {
        font-size: clamp(1.9rem, 3.5vw, 2.5rem);
        letter-spacing: -0.03em;
        margin: 0.5rem 0 1.5rem;
      }
      .prose {
        font-size: 1rem;
        line-height: 1.7;
        color: var(--ink);
      }
      .prose :is(h3) {
        font-size: 1.15rem;
        letter-spacing: -0.01em;
        margin: 2rem 0 0.6rem;
      }
      .prose p {
        color: var(--muted);
        margin: 0 0 0.9rem;
      }
      .prose code {
        font-family: var(--mono);
        font-size: 0.85em;
        background: var(--tint);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 0.05rem 0.35rem;
        color: var(--ink);
      }
      .prose pre {
        background: var(--soft);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1rem 1.1rem;
        overflow-x: auto;
        font-family: var(--mono);
        font-size: 0.82rem;
        line-height: 1.6;
        color: var(--ink);
        margin: 0 0 1.1rem;
      }
      .prose pre code {
        background: none;
        border: 0;
        padding: 0;
      }
      .prose ol,
      .prose ul {
        color: var(--muted);
        margin: 0 0 1rem;
        padding-left: 1.3rem;
        line-height: 1.7;
      }
      .prose li {
        margin: 0.25rem 0;
      }
      .prose .note {
        border-left: 3px solid var(--primary);
        background: color-mix(in srgb, var(--primary) 6%, transparent);
        padding: 0.7rem 1rem;
        border-radius: 0 8px 8px 0;
        font-size: 0.9rem;
      }
      .prose table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
        margin: 0 0 1rem;
      }
      .prose th,
      .prose td {
        text-align: left;
        padding: 0.55rem 0.7rem;
        border-bottom: 1px solid var(--border);
        vertical-align: top;
      }
      .prose th {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--muted);
      }
      button:focus-visible,
      input:focus-visible {
        outline: 2px solid var(--primary);
        outline-offset: 2px;
        border-radius: 8px;
      }
      @media (max-width: 820px) {
        .docs {
          grid-template-columns: 1fr;
        }
        .docs__side {
          position: static;
        }
      }
    `,
  ],
})
export class DocsComponent {
  readonly groups = DOC_GROUPS;
  readonly query = signal('');
  readonly activeId = signal<string>(DOC_TOPICS[0].id);

  readonly filtered = computed<DocTopic[]>(() => {
    const q = this.query().trim().toLowerCase();
    if (!q) return DOC_TOPICS;
    return DOC_TOPICS.filter((t) =>
      (t.title + ' ' + t.keywords + ' ' + t.html).toLowerCase().includes(q),
    );
  });

  readonly active = computed<DocTopic | undefined>(() => {
    const list = this.filtered();
    return list.find((t) => t.id === this.activeId()) ?? list[0];
  });

  topicsIn(group: string): DocTopic[] {
    return this.filtered().filter((t) => t.group === group);
  }

  select(id: string): void {
    this.activeId.set(id);
  }

  onSearch(ev: Event): void {
    this.query.set((ev.target as HTMLInputElement).value);
  }
}
