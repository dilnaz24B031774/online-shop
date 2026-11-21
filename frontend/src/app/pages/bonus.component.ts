import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { BONUS_COPY } from '../core/bonus-copy';
import { BonusCharacter, BonusCharacterId, BonusGift, BonusService, BonusState, Treat } from '../core/bonus.service';
import { I18nService } from '../core/i18n.service';
import { Mascot3dComponent, MascotPlay } from '../shared/mascot-3d.component';

@Component({
  selector: 'app-bonus',
  imports: [FormsModule, RouterLink, Mascot3dComponent],
  templateUrl: './bonus.component.html',
  styleUrl: './bonus.component.scss',
})
export class BonusComponent {
  readonly i = inject(I18nService);
  private readonly api = inject(BonusService);
  readonly copy = computed(() => BONUS_COPY[this.i.lang()]);
  readonly state = signal<BonusState | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  /** short "Rakhmet!" bubble after a mascot was treated */
  readonly cheer = signal<{ id: BonusCharacterId; text: string } | null>(null);
  readonly asking = signal<string | null>(null);      // gift waiting for an address
  /** tells a 3D mascot to eat, drink or jump; a new id replays the animation */
  readonly play = signal<MascotPlay | null>(null);
  readonly heroPlay = signal<MascotPlay | null>(null);
  /** "+5" floating above the mascot that was just treated */
  readonly gain = signal<{ id: BonusCharacterId; points: number; n: number } | null>(null);
  private plays = 0;
  address = '';
  readonly treats: Treat[] = ['kurt', 'kozhe'];
  private cheerTimer?: ReturnType<typeof setTimeout>;

  constructor() {
    this.api.state().subscribe({
      next: state => { this.state.set(state); this.loading.set(false); },
      error: () => { this.error.set(this.copy().errors['generic']); this.loading.set(false); },
    });
  }

  private animate(who: BonusCharacterId, action: MascotPlay['action']) {
    const play = { who, action, id: ++this.plays };
    this.play.set(play);
    this.heroPlay.set(play);
  }

  progress(character: BonusCharacter) {
    const goals = character.gifts.map(g => g.points);
    const next = character.next_goal;
    if (next === null) return 100;
    const previous = [0, ...goals].filter(goal => goal < next).pop() ?? 0;
    return Math.max(4, Math.round(((character.points - previous) / (next - previous)) * 100));
  }

  bubble(character: BonusCharacter) {
    const cheer = this.cheer();
    if (cheer?.id === character.id) return cheer.text;
    return character.points > 0 ? this.copy().happy[character.id] : this.copy().hungry[character.id];
  }

  /** give every treat in the bag: kurt first, then kozhe */
  feedAll(character: BonusCharacterId) {
    const s = this.state();
    if (!s) return;
    if (s.available.kurt) this.feed(character, 'kurt', true, () => this.feed(character, 'kozhe', true));
    else this.feed(character, 'kozhe', true);
  }

  feed(character: BonusCharacterId, treat: Treat, all = false, then?: () => void) {
    const available = this.state()?.available[treat] ?? 0;
    if (!available || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.api.feed(character, treat, all ? available : 1).subscribe({
      next: state => {
        const before = this.state()?.characters.find(c => c.id === character)?.points ?? 0;
        this.state.set(state);
        this.busy.set(false);
        this.animate(character, treat === 'kurt' ? 'eat' : 'drink');
        const after = state.characters.find(c => c.id === character)?.points ?? before;
        this.gain.set({ id: character, points: after - before, n: this.plays });
        then?.();
        const thanks = this.copy().thanks;
        this.cheer.set({ id: character, text: thanks[Math.floor(Math.random() * thanks.length)] });
        clearTimeout(this.cheerTimer);
        this.cheerTimer = setTimeout(() => this.cheer.set(null), 1800);
      },
      error: error => this.fail(error),
    });
  }

  claim(gift: BonusGift, address = '') {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.api.claim(gift.code, address).subscribe({
      next: state => {
        this.state.set(state); this.busy.set(false); this.asking.set(null); this.address = '';
        const owner = state.characters.find(c => c.gifts.some(g => g.code === gift.code));
        if (owner) this.animate(owner.id, 'happy');
      },
      error: (error: HttpErrorResponse) => {
        if (error.error?.detail === 'address_required') {
          this.busy.set(false);
          this.asking.set(gift.code);
          return;
        }
        this.fail(error);
      },
    });
  }

  sendWithAddress(gift: BonusGift) {
    if (this.address.trim().length < 5) { this.error.set(this.copy().errors['address_required']); return; }
    this.claim(gift, this.address.trim());
  }

  private fail(error: HttpErrorResponse) {
    this.busy.set(false);
    const code = error.error?.detail;
    this.error.set(this.copy().errors[code] ?? this.copy().errors['generic']);
  }
}
