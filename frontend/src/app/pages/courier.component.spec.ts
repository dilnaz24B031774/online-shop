import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';
import { CourierService } from '../core/courier.service';
import { CourierComponent } from './courier.component';

describe('Courier location consent and lifecycle', () => {
  const token = 'a'.repeat(43);
  let fragment: BehaviorSubject<string | null>;
  let api: jasmine.SpyObj<CourierService>;
  let onPosition: PositionCallback;
  let onError: PositionErrorCallback | null | undefined;
  let geolocation: jasmine.Spy;
  const position = {
    coords: { latitude: 43.24, longitude: 76.91, accuracy: 12 }, timestamp: Date.now(),
  } as GeolocationPosition;

  beforeEach(() => {
    fragment = new BehaviorSubject<string | null>(token);
    api = jasmine.createSpyObj<CourierService>('CourierService', ['session', 'locate']);
    api.session.and.returnValue(of({ order_id: 123, courier_name: 'Test courier', order_status: 'shipped', expires_at: new Date(Date.now() + 3600000).toISOString() }));
    api.locate.and.returnValue(of({ updated_at: new Date().toISOString() }));
    geolocation = spyOn(navigator.geolocation, 'getCurrentPosition').and.callFake((success, error) => {
      onPosition = success;
      onError = error;
    });
    TestBed.configureTestingModule({
      imports: [CourierComponent],
      providers: [provideRouter([]), { provide: ActivatedRoute, useValue: { fragment } }, { provide: CourierService, useValue: api }],
    });
  });

  function create() {
    const fixture = TestBed.createComponent(CourierComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('validates the link without requesting location before the courier starts', () => {
    const fixture = create();
    expect(api.session).toHaveBeenCalledOnceWith(token);
    expect(geolocation).not.toHaveBeenCalled();
    expect(api.locate).not.toHaveBeenCalled();
    fixture.destroy();
  });

  it('sends only the location obtained after an explicit start', () => {
    const fixture = create();
    fixture.componentInstance.start();
    expect(geolocation).toHaveBeenCalledTimes(1);
    expect(api.locate).not.toHaveBeenCalled();
    onPosition(position);
    expect(api.locate).toHaveBeenCalledOnceWith(token, position);
    expect(fixture.componentInstance.accuracy()).toBe(12);
    fixture.destroy();
  });

  it('does not send a pending position after sharing is stopped', () => {
    const fixture = create();
    fixture.componentInstance.start();
    fixture.componentInstance.stop();
    onPosition(position);
    expect(api.locate).not.toHaveBeenCalled();
    expect(fixture.componentInstance.sharing()).toBeFalse();
    fixture.destroy();
  });

  it('stops when permission is denied and never sends a fabricated location', () => {
    const fixture = create();
    fixture.componentInstance.start();
    onError?.({ code: 1, message: 'Denied' } as GeolocationPositionError);
    expect(fixture.componentInstance.sharing()).toBeFalse();
    expect(fixture.componentInstance.error()).toBe('denied');
    expect(api.locate).not.toHaveBeenCalled();
    fixture.destroy();
  });

  it('ignores a late location result after navigating away', () => {
    const fixture = create();
    fixture.componentInstance.start();
    fixture.destroy();
    onPosition(position);
    expect(api.locate).not.toHaveBeenCalled();
  });

  it('does not call the API or GPS for a missing sharing token', () => {
    fragment.next(null);
    const fixture = create();
    fixture.componentInstance.start();
    expect(api.session).not.toHaveBeenCalled();
    expect(geolocation).not.toHaveBeenCalled();
    expect(fixture.componentInstance.error()).toBe('invalid');
    fixture.destroy();
  });
});
