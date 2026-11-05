import { inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from './auth.service';

/** Sign-out action with a busy flag; call from a component's injection context. */
export function injectSignOut() {
  const auth = inject(AuthService);
  const router = inject(Router);
  const signingOut = signal(false);

  return {
    signingOut: signingOut.asReadonly(),
    async signOut(): Promise<void> {
      if (signingOut()) return;
      signingOut.set(true);
      try {
        await auth.logout();
      } catch {
        // Local session is cleared regardless; the server session expires on its own.
      } finally {
        signingOut.set(false);
        await router.navigateByUrl('/login', { replaceUrl: true });
      }
    },
  };
}
