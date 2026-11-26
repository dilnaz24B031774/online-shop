import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_URL } from './api.service';

export type BonusCharacterId = 'aisulu' | 'altai';
export type Treat = 'kurt' | 'kozhe';

export interface BonusGift {
  code: string;
  points: number;
  unlocked: boolean;
  status: 'requested' | 'sent' | null;
  claimed_at: string | null;
}

export interface BonusCharacter {
  id: BonusCharacterId;
  points: number;
  fed: Record<Treat, number>;
  next_goal: number | null;
  gifts: BonusGift[];
}

export interface BonusState {
  earned: Record<Treat, number>;
  available: Record<Treat, number>;
  characters: BonusCharacter[];
  rules: { kurt_every: string; kozhe_every: string; points: Record<Treat, number> };
}

@Injectable({ providedIn: 'root' })
export class BonusService {
  private readonly http = inject(HttpClient);

  state() {
    return this.http.get<BonusState>(`${API_URL}/bonus/`);
  }

  feed(character: BonusCharacterId, treat: Treat, quantity: number) {
    return this.http.post<BonusState>(`${API_URL}/bonus/feed/`, { character, treat, quantity });
  }

  claim(gift: string, address = '') {
    return this.http.post<BonusState>(`${API_URL}/bonus/claim/`, { gift, address });
  }
}
