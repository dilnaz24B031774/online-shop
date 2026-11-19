/**
 * Frontend tests for the online shop (Angular + Karma + Jasmine) - everything in one file.
 * Run from the frontend folder:   npm test
 * Test data (fake products, cart, user) is at the top; each block below tests one part of the site.
 */
import { HttpClient, HttpErrorResponse, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed, discardPeriodicTasks, fakeAsync, tick } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { API_URL, ApiService } from '../app/core/api.service';
import { authGuard } from '../app/core/auth.guard';
import { authInterceptor } from '../app/core/auth.interceptor';
import { AuthService } from '../app/core/auth.service';
import { CartService } from '../app/core/cart.service';
import { I18nService } from '../app/core/i18n.service';
import { Cart, Category, Product, User } from '../app/core/models';
import { CartComponent } from '../app/pages/cart.component';
import { CheckoutComponent } from '../app/pages/checkout.component';
import { LoginComponent } from '../app/pages/login.component';
import { RegisterComponent } from '../app/pages/register.component';
import { ProductCardComponent } from '../app/shared/product-card.component';
import { StarsComponent } from '../app/shared/stars.component';

// ---- fake data used by the tests ----
const CATEGORY: Category = { id: 1, name_en: 'Laptops', name_ru: 'Ноутбуки', name_kk: 'Ноутбуктер' };

function makeProduct(over: Partial<Product> = {}): Product {
  return {
    id: 1, sku: 'LAP-1', name_en: 'Laptop', name_ru: 'Ноутбук', name_kk: '', description_en: '', description_ru: '',
    description_kk: '', price: '999.00', stock_quantity: 5, brand: 'Acme', image_url: '', category: CATEGORY,
    avg_rating: 4.5, review_count: 2, ...over,
  };
}

function makeCart(quantity = 1, product = makeProduct()): Cart {
  const total = (Number(product.price) * quantity).toFixed(2);
  return { items: quantity ? [{ id: 1, product, quantity, line_total: total }] : [], total, count: quantity };
}

const USER: User = {
  id: 1, username: 'aigerim', email: 'a@b.kz', first_name: 'Aigerim', last_name: '', phone: '',
  role: 'customer', preferred_language: 'en',
};

// ======================================================================
// AuthService, authGuard, authInterceptor
// ======================================================================
describe('AuthService, authGuard, authInterceptor', () => {
  let http: HttpTestingController;
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(withInterceptors([authInterceptor])), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });
  afterEach(() => { http.verify(); localStorage.clear(); });

  function loginOk() {
    auth.login('aigerim', 'secret123').subscribe();
    http.expectOne(`${API_URL}/auth/login/`).flush({ access: 'ACC', refresh: 'REF' });
    http.expectOne(`${API_URL}/me/`).flush(USER);
  }

  it('starts logged out', () => {
    expect(auth.isLoggedIn()).toBeFalse();
    expect(auth.user()).toBeNull();
  });

  it('login saves tokens in localStorage and loads the user', () => {
    loginOk();
    expect(auth.isLoggedIn()).toBeTrue();
    expect(auth.user()?.username).toBe('aigerim');
    expect(localStorage.getItem('sauda.access')).toBe('ACC');
    expect(localStorage.getItem('sauda.refresh')).toBe('REF');
  });

  it('register stores tokens and the new user', () => {
    auth.register({ username: 'new', email: 'n@b.kz', password: 'Str0ngPass!' }).subscribe();
    http.expectOne(`${API_URL}/auth/register/`).flush({ access: 'A', refresh: 'R', user: USER });
    expect(auth.isLoggedIn()).toBeTrue();
    expect(auth.user()).toEqual(USER);
  });

  it('logout clears tokens and the user', () => {
    loginOk();
    auth.logout(false);
    expect(auth.isLoggedIn()).toBeFalse();
    expect(auth.user()).toBeNull();
    expect(localStorage.getItem('sauda.access')).toBeNull();
  });

  it('authGuard lets a logged-in user through', () => {
    loginOk();
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/cart' } as never));
    expect(result).toBeTrue();
  });

  it('authGuard redirects a guest to /login with returnUrl', () => {
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/cart' } as never));
    expect(router.serializeUrl(result as never)).toBe('/login?returnUrl=%2Fcart');
  });

  it('interceptor adds the Bearer token to our API requests', () => {
    loginOk();
    TestBed.inject(HttpClient).get(`${API_URL}/cart/`).subscribe();
    const req = http.expectOne(`${API_URL}/cart/`);
    expect(req.request.headers.get('Authorization')).toBe('Bearer ACC');
    req.flush({});
  });

  it('interceptor does NOT send the token to login or to other sites', () => {
    loginOk();
    const client = TestBed.inject(HttpClient);
    client.post(`${API_URL}/auth/login/`, {}).subscribe();
    expect(http.expectOne(`${API_URL}/auth/login/`).request.headers.has('Authorization')).toBeFalse();
    client.get('https://example.com/x').subscribe();
    expect(http.expectOne('https://example.com/x').request.headers.has('Authorization')).toBeFalse();
  });

  it('interceptor logs out and goes to /login on 401', () => {
    loginOk();
    const nav = spyOn(router, 'navigate').and.resolveTo(true);
    TestBed.inject(HttpClient).get(`${API_URL}/orders/`).subscribe({ error: () => {} });
    http.expectOne(`${API_URL}/orders/`).flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.isLoggedIn()).toBeFalse();
    expect(nav).toHaveBeenCalled();
  });
});

// ======================================================================
// CartService
// ======================================================================
describe('CartService', () => {
  let http: HttpTestingController;
  let cart: CartService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    cart = TestBed.inject(CartService);
  });
  afterEach(() => http.verify());

  it('is empty for a guest (count = 0, quantityOf = 0)', () => {
    expect(cart.count()).toBe(0);
    expect(cart.quantityOf(1)).toBe(0);
  });

  it('load() fills the cart and the badge count', () => {
    cart.load().subscribe();
    http.expectOne(`${API_URL}/cart/`).flush(makeCart(3));
    expect(cart.count()).toBe(3);
    expect(cart.quantityOf(1)).toBe(3);
  });

  it('add() sends current quantity + 1', () => {
    cart.cart.set(makeCart(2, makeProduct({ id: 7 })));
    cart.add(7).subscribe();
    const req = http.expectOne(`${API_URL}/cart/`);
    expect(req.request.body).toEqual({ product_id: 7, quantity: 3 });
    req.flush(makeCart(3, makeProduct({ id: 7 })));
    expect(cart.quantityOf(7)).toBe(3);
  });

  it('setQuantity(…, 0) removes the item', () => {
    cart.setQuantity(1, 0).subscribe();
    http.expectOne(`${API_URL}/cart/`).flush(makeCart(0));
    expect(cart.count()).toBe(0);
  });
});

// ======================================================================
// I18nService
// ======================================================================
describe('I18nService', () => {
  let i18n: I18nService;

  beforeEach(() => {
    localStorage.clear();
    i18n = TestBed.inject(I18nService);
  });
  afterEach(() => { localStorage.clear(); document.documentElement.lang = 'en'; });

  it('uses English by default', () => {
    expect(i18n.lang()).toBe('en');
    expect(i18n.t('cart.title')).toBe('Your cart');
  });

  it('use() switches language, <html lang> and remembers the choice', () => {
    i18n.use('ru');
    expect(i18n.t('cart.title')).toBe('Корзина');
    expect(document.documentElement.lang).toBe('ru');
    expect(localStorage.getItem('sauda.lang')).toBe('ru');
  });

  it('returns the key itself when there is no translation', () => {
    expect(i18n.t('no.such.key')).toBe('no.such.key');
  });

  it('replaces {params}', () => {
    expect(i18n.t('checkout.accepted', { n: 42 })).toBe('Order #42 is accepted');
  });

  it('pick() uses the current language and falls back to English', () => {
    const p = { name_en: 'Laptop', name_ru: 'Ноутбук', name_kk: '' };
    i18n.use('ru');
    expect(i18n.pick(p)).toBe('Ноутбук');
    i18n.use('kk');
    expect(i18n.pick(p)).toBe('Laptop');   // kk is empty -> English
    expect(i18n.pick(null)).toBe('');
  });
});

// ======================================================================
// Shared components
// ======================================================================
describe('StarsComponent', () => {
  function render(value: number | null, count: number | null = null) {
    const f = TestBed.createComponent(StarsComponent);
    f.componentRef.setInput('value', value);
    f.componentRef.setInput('count', count);
    f.detectChanges();
    return f.nativeElement as HTMLElement;
  }

  it('draws 5 stars and fills the rounded rating', () => {
    const el = render(3.6);
    expect(el.querySelectorAll('svg').length).toBe(5);
    expect(el.querySelectorAll('svg.on').length).toBe(4);
  });

  it('shows "–" when there is no rating yet', () => {
    const el = render(null, 0);
    expect(el.querySelectorAll('svg.on').length).toBe(0);
    expect(el.querySelector('.count')?.textContent).toContain('–');
  });

  it('shows rating and review count', () => {
    expect(render(4.5, 12).querySelector('.count')?.textContent?.replace(/\s+/g, ' ').trim()).toBe('4.5 (12)');
  });
});

describe('ProductCardComponent', () => {
  let http: HttpTestingController;
  let router: Router;

  function render(p: Product): ComponentFixture<ProductCardComponent> {
    const f = TestBed.createComponent(ProductCardComponent);
    f.componentRef.setInput('product', p);
    f.detectChanges();
    return f;
  }
  const text = (f: ComponentFixture<unknown>) => (f.nativeElement as HTMLElement).textContent ?? '';

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });
  afterEach(() => { localStorage.clear(); });

  it('shows name, price and brand', () => {
    const f = render(makeProduct());
    expect(text(f)).toContain('Laptop');
    expect(text(f)).toContain('$999.00');
    expect(text(f)).toContain('Acme');
  });

  it('shows the "only N left" badge when stock is below 10', () => {
    expect(text(render(makeProduct({ stock_quantity: 3 })))).toContain('3');
    expect((render(makeProduct({ stock_quantity: 3 })).nativeElement as HTMLElement).querySelector('.badge.low')).not.toBeNull();
    expect((render(makeProduct({ stock_quantity: 50 })).nativeElement as HTMLElement).querySelector('.badge.low')).toBeNull();
  });

  it('shows "Sold out" instead of the cart button when stock is 0', () => {
    const f = render(makeProduct({ stock_quantity: 0 }));
    expect(text(f)).toContain('Sold out');
    expect((f.nativeElement as HTMLElement).querySelector('button.add')).toBeNull();
  });

  it('guest clicking "Add to cart" is sent to /login', () => {
    const nav = spyOn(router, 'navigate').and.resolveTo(true);
    const f = render(makeProduct());
    ((f.nativeElement as HTMLElement).querySelector('button.add') as HTMLButtonElement).click();
    expect(nav.calls.mostRecent().args[0]).toEqual(['/login']);
    http.expectNone(`${API_URL}/cart/`);
  });

  it('logged-in user clicking "Add to cart" posts to /cart/', () => {
    localStorage.setItem('sauda.access', 'T');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    expect(TestBed.inject(AuthService).isLoggedIn()).toBeTrue();
    TestBed.inject(CartService).cart.set(makeCart(0));
    const f = render(makeProduct({ id: 9 }));
    ((f.nativeElement as HTMLElement).querySelector('button.add') as HTMLButtonElement).click();
    const reqs = http.match(`${API_URL}/cart/`).filter(r => r.request.method === 'POST');
    expect(reqs.length).toBe(1);
    expect(reqs[0].request.body).toEqual({ product_id: 9, quantity: 1 });
    http.match(() => true).forEach(r => r.flush(makeCart(1)));
  });
});

// ======================================================================
// LoginComponent
// ======================================================================
describe('LoginComponent', () => {
  let f: ComponentFixture<LoginComponent>;
  let c: LoginComponent;
  let auth: jasmine.SpyObj<AuthService>;
  let api: jasmine.SpyObj<ApiService>;
  let router: Router;

  beforeEach(() => {
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['login']);
    api = jasmine.createSpyObj<ApiService>('ApiService', ['securityChallenge']);
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: auth }, { provide: ApiService, useValue: api }],
    });
    router = TestBed.inject(Router);
    spyOn(router, 'navigateByUrl').and.resolveTo(true);
    f = TestBed.createComponent(LoginComponent);
    c = f.componentInstance;
    f.detectChanges();
  });

  const fail = (status: number, error: unknown = {}) => throwError(() => new HttpErrorResponse({ status, error }));

  it('empty form shows "fill all fields" and does not call the server', () => {
    c.submit();
    expect(c.errorKey()).toBe('auth.fillFields');
    expect(auth.login).not.toHaveBeenCalled();
  });

  it('successful login goes to returnUrl and clears the password', () => {
    auth.login.and.returnValue(of(USER));
    f.componentRef.setInput('returnUrl', '/orders');
    c.username = ' aigerim ';
    c.password = 'secret123';
    c.submit();
    expect(auth.login.calls.mostRecent().args[0]).toBe('aigerim');      // trimmed
    expect(router.navigateByUrl).toHaveBeenCalledWith('/orders');
    expect(c.password).toBe('');
  });

  it('wrong password (401) shows an error and re-enables the button', () => {
    auth.login.and.returnValue(fail(401));
    c.username = 'a'; c.password = 'b';
    c.submit();
    expect(c.errorKey()).toBe('auth.wrong');
    expect(c.busy()).toBeFalse();
  });

  it('server asking for a challenge loads it', () => {
    auth.login.and.returnValue(fail(401, { challenge_required: true, remaining_attempts: 2 }));
    api.securityChallenge.and.returnValue(of({ id: 'x', prompt: '2+2', expires_in: 60 }));
    c.username = 'a'; c.password = 'b';
    c.submit();
    expect(c.challengeRequired()).toBeTrue();
    expect(c.challenge()?.id).toBe('x');
    expect(c.remainingAttempts()).toBe(2);
  });

  it('429 starts a cooldown timer shown as m:ss', fakeAsync(() => {
    auth.login.and.returnValue(fail(429, { retry_after: 90 }));
    c.username = 'a'; c.password = 'b';
    c.submit();
    expect(c.cooldownSeconds()).toBe(90);
    expect(c.cooldownText()).toBe('1:30');
    tick(2000);
    expect(c.cooldownSeconds()).toBeLessThan(90);
    discardPeriodicTasks();
  }));

  it('safeReturnUrl blocks open redirects', () => {
    for (const bad of ['//evil.com', 'https://evil.com', '/a\\b', 'javascript:alert(1)']) {
      f.componentRef.setInput('returnUrl', bad);
      expect(c.safeReturnUrl()).withContext(bad).toBe('/');
    }
    f.componentRef.setInput('returnUrl', '/cart?x=1');
    expect(c.safeReturnUrl()).toBe('/cart?x=1');
  });
});

// ======================================================================
// RegisterComponent
// ======================================================================
describe('RegisterComponent', () => {
  let f: ComponentFixture<RegisterComponent>;
  let c: RegisterComponent;
  let auth: jasmine.SpyObj<AuthService>;

  beforeEach(() => {
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['register']);
    TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: AuthService, useValue: auth }] });
    f = TestBed.createComponent(RegisterComponent);
    c = f.componentInstance;
    f.detectChanges();
  });

  it('renders username, email and password fields', () => {
    const el = f.nativeElement as HTMLElement;
    for (const name of ['username', 'email', 'password']) expect(el.querySelector(`input[name="${name}"]`)).withContext(name).not.toBeNull();
    expect((el.querySelector('input[name="password"]') as HTMLInputElement).type).toBe('password');
  });

  it('refuses to submit an empty form', () => {
    c.submit();
    expect(c.errors().length).toBe(1);
    expect(auth.register).not.toHaveBeenCalled();
  });

  it('registers and navigates to returnUrl', () => {
    const nav = spyOn(TestBed.inject(Router), 'navigateByUrl').and.resolveTo(true);
    auth.register.and.returnValue(of(USER));
    Object.assign(c.form, { username: 'new', email: 'n@b.kz', password: 'Str0ngPass!' });
    c.submit();
    expect(nav).toHaveBeenCalledWith('/');
  });

  it('shows every password-rule message returned by the backend', () => {
    auth.register.and.returnValue(throwError(() => new HttpErrorResponse({
      status: 400, error: { password: ['Too short.', 'Too common.'], email: ['Invalid email.'] },
    })));
    Object.assign(c.form, { username: 'new', email: 'bad', password: '1' });
    c.submit();
    f.detectChanges();
    expect(c.errors()).toEqual(['Too short.', 'Too common.', 'Invalid email.']);
    expect((f.nativeElement as HTMLElement).querySelectorAll('.alert-error div').length).toBe(3);
    expect(c.busy()).toBeFalse();
  });
});

// ======================================================================
// CartComponent
// ======================================================================
describe('CartComponent', () => {
  let f: ComponentFixture<CartComponent>;
  let http: HttpTestingController;
  const el = () => f.nativeElement as HTMLElement;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    f = TestBed.createComponent(CartComponent);
    f.detectChanges();                         // ngOnInit -> GET /cart/
  });
  afterEach(() => {
    http.match('products/manifest.json').forEach(r => r.flush({}));   // product images ask for the local photo list
    http.verify();
  });

  const load = (cart: Cart) => { http.expectOne(`${API_URL}/cart/`).flush(cart); f.detectChanges(); };

  it('shows "loading" until the cart arrives', () => {
    expect(el().textContent).toContain('Loading');
    load(makeCart(1));
  });

  it('shows the empty-cart message', () => {
    load(makeCart(0));
    expect(el().textContent).toContain('Your cart is empty');
    expect(el().querySelector('.summary')).toBeNull();
  });

  it('lists items and the total', () => {
    load(makeCart(2));
    expect(el().querySelectorAll('article.row').length).toBe(1);
    expect(el().querySelector('.line')?.textContent).toContain('1998.00');
    expect(el().querySelector('.total strong')?.textContent).toContain('1998.00');
  });

  it('"+" is disabled when quantity reaches the stock', () => {
    load(makeCart(5, makeProduct({ stock_quantity: 5 })));
    const plus = el().querySelectorAll<HTMLButtonElement>('.stepper button')[1];
    expect(plus.disabled).toBeTrue();
  });

  it('"+" sends quantity + 1', () => {
    load(makeCart(1));
    el().querySelectorAll<HTMLButtonElement>('.stepper button')[1].click();
    const req = http.expectOne(`${API_URL}/cart/`);
    expect(req.request.body).toEqual({ product_id: 1, quantity: 2 });
    req.flush(makeCart(2));
  });

  it('"Remove" sends quantity 0', () => {
    load(makeCart(1));
    el().querySelector<HTMLButtonElement>('.remove')!.click();
    const req = http.expectOne(`${API_URL}/cart/`);
    expect(req.request.body.quantity).toBe(0);
    req.flush(makeCart(0));
  });

  it('shows the server error text when the update is rejected', () => {
    load(makeCart(1));
    el().querySelectorAll<HTMLButtonElement>('.stepper button')[1].click();
    http.expectOne(`${API_URL}/cart/`).flush({ detail: 'Not enough stock.' }, { status: 400, statusText: 'Bad Request' });
    f.detectChanges();
    expect(el().querySelector('.alert-error')?.textContent).toContain('Not enough stock.');
  });
});

// ======================================================================
// CheckoutComponent
// ======================================================================
const ADDRESS = { id: 3, label: 'Home', city: 'Almaty', street: 'Abay 1', apartment: '', postal_code: '', is_default: true };

describe('CheckoutComponent (card form and payment)', () => {
  let f: ComponentFixture<CheckoutComponent>;
  let c: CheckoutComponent;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    f = TestBed.createComponent(CheckoutComponent);
    c = f.componentInstance;
    f.detectChanges();                                           // ngOnInit
    http.expectOne(`${API_URL}/cart/`).flush(makeCart(2));
    http.expectOne(`${API_URL}/addresses/`).flush([ADDRESS]);
  });
  afterEach(() => http.verify());

  function fillCard(number = '4242424242424242', expiry = '1230', cvc = '123') {
    c.setNumber(number); c.setExpiry(expiry); c.card.holder = 'AIGERIM K'; c.card.cvc = cvc;
  }

  it('selects the default address automatically', () => expect(c.addressId).toBe(3));

  it('setNumber groups digits by 4 and detects the card brand', () => {
    c.setNumber('4242424242424242');
    expect(c.card.number).toBe('4242 4242 4242 4242');
    expect(c.brand()).toBe('visa');
    c.setNumber('5555 abc 5555');
    expect(c.card.number).toBe('5555 5555');
    expect(c.brand()).toBe('mastercard');
    c.setNumber('2200 1234');
    expect(c.brand()).toBe('mir');
    c.setNumber('371449635398431');
    expect(c.brand()).toBe('amex');
  });

  it('setExpiry formats MM/YY', () => {
    c.setExpiry('1230');
    expect(c.card.expiry).toBe('12/30');
  });

  it('monthly() divides the total by the months', () => {
    c.installmentMonths = 6;
    expect(c.monthly()).toBe('333.00');                         // 1998 / 6
  });

  const cases: [string, () => void, string][] = [
    ['number (fails Luhn)', () => fillCard('4242424242424241'), 'number'],
    ['holder', () => { fillCard(); c.card.holder = 'A'; }, 'holder'],
    ['expiry (past date)', () => fillCard('4242424242424242', '0120'), 'expiry'],
    ['expiry (month 13)', () => fillCard('4242424242424242', '1330'), 'expiry'],
    ['cvc', () => fillCard('4242424242424242', '1230', '12'), 'cvc'],
  ];
  cases.forEach(([name, setup, field]) => {
    it(`invalid ${name} blocks the order and sends nothing`, () => {
      setup();
      c.place();
      expect(c.cardError()).toBe(field);
      expect(c.error()).not.toBe('');
    });
  });

  it('valid card posts the order and clears the card data', () => {
    fillCard();
    c.place();
    const req = http.expectOne(`${API_URL}/checkout/`);
    expect(req.request.body.address_id).toBe(3);
    expect(req.request.body.card.exp_year).toBe(2030);
    req.flush({ id: 11, status: 'paid' });
    http.expectOne(`${API_URL}/cart/`).flush(makeCart(0));
    expect(c.placed()?.id).toBe(11);
    expect(c.card).toEqual({ number: '', holder: '', expiry: '', cvc: '' });
  });

  it('bank decline (402) shows the declined message and clears the CVC', () => {
    fillCard();
    c.place();
    http.expectOne(`${API_URL}/checkout/`).flush({}, { status: 402, statusText: 'Payment Required' });
    expect(c.error()).toContain('declined');
    expect(c.card.cvc).toBe('');
    expect(c.busy()).toBeFalse();
  });

  it('cash on delivery needs no card', () => {
    c.method = 'cash_on_delivery';
    c.place();
    expect(http.expectOne(`${API_URL}/checkout/`).request.body.card).toBeUndefined();
  });

  it('placing an order without an address shows an error', () => {
    c.addressId = null;
    c.place();
    expect(c.error()).not.toBe('');
  });

  it('applyPromo shows the server error for a wrong code', () => {
    c.promoCode = 'BAD';
    c.applyPromo();
    http.expectOne(`${API_URL}/promo/check/`).flush({ detail: 'Unknown promo code.' }, { status: 400, statusText: 'Bad Request' });
    expect(c.promoError()).toBe('Unknown promo code.');
    expect(c.promo()).toBeNull();
  });
});