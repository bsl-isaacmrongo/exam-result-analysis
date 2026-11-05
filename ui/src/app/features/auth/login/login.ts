import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  Injector,
  afterNextRender,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import {
  AuthService,
  authErrorMessage,
  googleSsoErrorMessage,
} from '../../../core/auth/auth.service';
import { safeReturnUrl } from '../../../core/auth/return-url';

type LoginMode = 'google' | 'password';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'flex flex-1 flex-col' },
})
export class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly injector = inject(Injector);

  private readonly emailInput = viewChild<ElementRef<HTMLInputElement>>('emailInput');

  protected readonly busy = signal<'password' | 'google' | null>(null);
  protected readonly error = signal<string | null>(
    googleSsoErrorMessage(this.route.snapshot.queryParamMap.get('error')),
  );
  protected readonly showPassword = signal(false);
  protected readonly showForgotHint = signal(false);
  /** Google is the default; email + password is the fallback. */
  protected readonly mode = signal<LoginMode>('google');
  protected readonly sessionExpired = this.route.snapshot.queryParamMap.get('reason') === 'expired';

  private readonly returnUrl = safeReturnUrl(this.route.snapshot.queryParamMap.get('returnUrl'));
  protected readonly googleLoginUrl = this.auth.googleLoginUrl(this.returnUrl);

  protected readonly form = inject(NonNullableFormBuilder).group({
    email: ['', [Validators.required, Validators.email, Validators.maxLength(320)]],
    password: ['', [Validators.required, Validators.maxLength(256)]],
  });

  /** Full-page navigation to the API, which redirects to Google. */
  protected startGoogle(event: MouseEvent): void {
    if (this.busy()) {
      event.preventDefault();
      return;
    }
    this.error.set(null);
    this.busy.set('google');
  }

  /** Coming back via the browser's Back button restores a frozen page. */
  @HostListener('window:pageshow', ['$event'])
  protected onPageShow(event: PageTransitionEvent): void {
    if (event.persisted) this.busy.set(null);
  }

  protected async submitPassword(): Promise<void> {
    if (this.busy()) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.error.set(null);
    this.busy.set('password');
    const { email, password } = this.form.getRawValue();
    try {
      await this.auth.loginWithPassword(email, password);
      await this.redirectAfterLogin();
    } catch (err) {
      this.error.set(authErrorMessage(err));
      this.form.controls.password.reset();
    } finally {
      this.busy.set(null);
    }
  }

  protected usePassword(): void {
    this.error.set(null);
    this.mode.set('password');
    afterNextRender(() => this.emailInput()?.nativeElement.focus(), {
      injector: this.injector,
    });
  }

  protected showError(control: 'email' | 'password'): boolean {
    const c = this.form.controls[control];
    return c.invalid && (c.touched || c.dirty);
  }

  private redirectAfterLogin(): Promise<boolean> {
    return this.router.navigateByUrl(this.returnUrl, { replaceUrl: true });
  }
}
