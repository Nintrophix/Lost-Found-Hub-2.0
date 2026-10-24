import { provideHttpClient, withFetch, withInterceptors, withXsrfConfiguration } from '@angular/common/http';
import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling, withViewTransitions } from '@angular/router';

import { routes } from './app.routes';
import { Auth, sessionExpiryInterceptor } from './core/auth';
import { NotificationFeed } from './core/notification-feed';
import { SmoothScroll } from './core/smooth-scroll';
import { Seo } from './core/seo';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      routes,
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'top' }),
      withViewTransitions({
        skipInitialTransition: true,
        onViewTransitionCreated: ({ transition }) => {
          // Browsers refuse transitions in hidden tabs and reject their promises with InvalidStateError.
          // A skipped transition is a normal outcome, not an error, so skip early and swallow the rejection.
          const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
          if (document.visibilityState === 'hidden' || reduced) transition.skipTransition();
          transition.ready.catch(() => undefined);
          transition.finished.catch(() => undefined);
          transition.updateCallbackDone.catch(() => undefined);
        },
      }),
    ),
    // The backend sets XSRF-TOKEN and expects X-XSRF-TOKEN on writes (these are also Angular's defaults).
    provideHttpClient(
      withFetch(),
      withXsrfConfiguration({ cookieName: 'XSRF-TOKEN', headerName: 'X-XSRF-TOKEN' }),
      withInterceptors([sessionExpiryInterceptor]),
    ),
    provideAppInitializer(() => {
      inject(Seo).init();
      inject(NotificationFeed).start();
      inject(SmoothScroll).start();
      return inject(Auth).load();
    }),
  ],
};
