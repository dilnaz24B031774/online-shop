import type { Lang } from './i18n.service';
import type { BonusCharacterId, Treat } from './bonus.service';

export interface BonusCopy {
  nav: string; eyebrow: string; title: string; intro: string;
  step1: string; step2: string; step3: string;
  bag: string; bagHint: string; treats: Record<Treat, string>; treatsShort: Record<Treat, string>;
  earnedHint: (kurtEvery: string, kozheEvery: string) => string;
  names: Record<BonusCharacterId, string>;
  roles: Record<BonusCharacterId, string>;
  give: (treat: string) => string; giveAll: string; points: string;
  toNext: (left: number) => string; allDone: string;
  hungry: Record<BonusCharacterId, string>; happy: Record<BonusCharacterId, string>; thanks: string[];
  gifts: Record<string, string>; giftsTitle: string;
  claim: string; locked: (points: number) => string; requested: string; sent: string;
  addressLabel: string; addressHint: string; send: string; cancel: string;
  errors: Record<string, string>; loading: string; empty: string; shop: string;
}

const EN: BonusCopy = {
  nav: 'Bonuses', eyebrow: 'SaudaGo dastarkhan', title: 'Treat our friends, get SaudaGo merch',
  intro: 'Every paid order brings you kurt and Nauryz kozhe. Treat Aisulu and Altai — when they are full, they send you a gift.',
  step1: 'Shop and pay', step2: 'Get kurt and Nauryz kozhe', step3: 'Treat a friend and collect gifts',
  bag: 'Your treats', bagHint: 'Ready to give', treats: { kurt: 'Kurt', kozhe: 'Nauryz kozhe' },
  treatsShort: { kurt: 'kurt', kozhe: 'kozhe' },
  earnedHint: (k, z) => `1 kurt for every $${k} and 1 bowl of Nauryz kozhe for every $${z} of a paid order. Kurt = 1 point, kozhe = 5 points.`,
  names: { aisulu: 'Aisulu', altai: 'Altai' },
  roles: { aisulu: 'loves kurt and stickers', altai: 'never says no to kozhe' },
  give: t => `Give ${t}`, giveAll: 'Give everything', points: 'points',
  toNext: left => `${left} points to the next gift`, allDone: 'All gifts collected — rakhmet!',
  hungry: { aisulu: 'Sälem! I am a little hungry…', altai: 'Is that kozhe I smell?' },
  happy: { aisulu: 'Delicious! Thank you!', altai: 'Rakhmet, that was great!' },
  thanks: ['Rakhmet!', 'Delicious!', 'More, please!', 'Yum!'],
  giftsTitle: 'Gifts',
  gifts: {
    aisulu_stickers: 'Aisulu sticker pack', aisulu_keychain: 'Aisulu keychain',
    aisulu_tote: 'SaudaGo tote bag with ornament', aisulu_hoodie: 'SaudaGo hoodie',
    altai_badge: 'Altai pin badge', altai_mug: 'Altai mug', altai_cap: 'SaudaGo cap', altai_tshirt: 'SaudaGo T-shirt',
  },
  claim: 'Get gift', locked: p => `${p} points`, requested: 'Being prepared', sent: 'Sent',
  addressLabel: 'Where should we send the gift?', addressHint: 'City, street, house, flat', send: 'Send', cancel: 'Cancel',
  errors: {
    not_enough_treats: 'Not enough treats for that.', gift_locked: 'This gift is not unlocked yet.',
    already_claimed: 'You already asked for this gift.', address_required: 'Please enter a delivery address.',
    generic: 'Something went wrong. Please try again.',
  },
  loading: 'Setting the dastarkhan…', empty: 'No treats yet — your next paid order will bring some.', shop: 'Go shopping',
};

const RU: BonusCopy = {
  ...EN,
  nav: 'Бонусы', eyebrow: 'Дастархан SaudaGo', title: 'Угощайте друзей — получайте мерч SaudaGo',
  intro: 'За каждый оплаченный заказ вы получаете құрт и наурыз көже. Угощайте Айсұлу и Алтая — когда они сыты, они дарят подарки.',
  step1: 'Покупайте и оплачивайте', step2: 'Получайте құрт и наурыз көже', step3: 'Угощайте друга и забирайте подарки',
  bag: 'Ваши угощения', bagHint: 'Можно угостить', treats: { kurt: 'Құрт', kozhe: 'Наурыз көже' },
  treatsShort: { kurt: 'құрт', kozhe: 'көже' },
  earnedHint: (k, z) => `1 құрт за каждые $${k} и 1 пиала наурыз көже за каждые $${z} оплаченного заказа. Құрт = 1 очко, көже = 5 очков.`,
  names: { aisulu: 'Айсұлу', altai: 'Алтай' },
  roles: { aisulu: 'обожает құрт и стикеры', altai: 'никогда не откажется от көже' },
  give: t => `Дать ${t}`, giveAll: 'Отдать всё', points: 'очков',
  toNext: left => `Ещё ${left} очков до подарка`, allDone: 'Все подарки собраны — рақмет!',
  hungry: { aisulu: 'Сәлем! Я немного проголодалась…', altai: 'Это пахнет наурыз көже?' },
  happy: { aisulu: 'Как вкусно! Спасибо!', altai: 'Рақмет, вот это угощение!' },
  thanks: ['Рақмет!', 'Вкусно!', 'Ещё, пожалуйста!', 'Ммм!'],
  giftsTitle: 'Подарки',
  gifts: {
    aisulu_stickers: 'Стикерпак с Айсұлу', aisulu_keychain: 'Брелок Айсұлу',
    aisulu_tote: 'Шоппер SaudaGo с орнаментом', aisulu_hoodie: 'Худи SaudaGo',
    altai_badge: 'Значок с Алтаем', altai_mug: 'Кружка Алтай', altai_cap: 'Кепка SaudaGo', altai_tshirt: 'Футболка SaudaGo',
  },
  claim: 'Забрать', locked: p => `${p} очков`, requested: 'Готовим к отправке', sent: 'Отправлен',
  addressLabel: 'Куда отправить подарок?', addressHint: 'Город, улица, дом, квартира', send: 'Отправить', cancel: 'Отмена',
  errors: {
    not_enough_treats: 'Не хватает угощений.', gift_locked: 'Этот подарок ещё не открыт.',
    already_claimed: 'Вы уже запросили этот подарок.', address_required: 'Укажите адрес доставки.',
    generic: 'Что-то пошло не так. Попробуйте ещё раз.',
  },
  loading: 'Накрываем дастархан…', empty: 'Пока угощений нет — они появятся после оплаченного заказа.', shop: 'За покупками',
};

const KK: BonusCopy = {
  ...EN,
  nav: 'Бонустар', eyebrow: 'SaudaGo дастарханы', title: 'Достарды сыйлаңыз — SaudaGo мерчін алыңыз',
  intro: 'Әр төленген тапсырыс үшін құрт пен наурыз көже аласыз. Айсұлу мен Алтайды сыйлаңыз — тойғанда олар сыйлық береді.',
  step1: 'Сатып алып, төлеңіз', step2: 'Құрт пен наурыз көже алыңыз', step3: 'Досыңызды сыйлап, сыйлық алыңыз',
  bag: 'Сіздің тағамдарыңыз', bagHint: 'Беруге дайын', treats: { kurt: 'Құрт', kozhe: 'Наурыз көже' },
  treatsShort: { kurt: 'құрт', kozhe: 'көже' },
  earnedHint: (k, z) => `Төленген тапсырыстың әр $${k} үшін 1 құрт, әр $${z} үшін 1 кесе наурыз көже. Құрт = 1 ұпай, көже = 5 ұпай.`,
  names: { aisulu: 'Айсұлу', altai: 'Алтай' },
  roles: { aisulu: 'құрт пен стикерді жақсы көреді', altai: 'көжеден ешқашан бас тартпайды' },
  give: t => `${t} беру`, giveAll: 'Бәрін беру', points: 'ұпай',
  toNext: left => `Сыйлыққа дейін тағы ${left} ұпай`, allDone: 'Барлық сыйлық жиналды — рақмет!',
  hungry: { aisulu: 'Сәлем! Сәл қарным ашты…', altai: 'Наурыз көженің иісі ме?' },
  happy: { aisulu: 'Қандай дәмді! Рақмет!', altai: 'Рақмет, керемет дәм!' },
  thanks: ['Рақмет!', 'Дәмді!', 'Тағы беріңізші!', 'Ммм!'],
  giftsTitle: 'Сыйлықтар',
  gifts: {
    aisulu_stickers: 'Айсұлу стикерпагы', aisulu_keychain: 'Айсұлу брелогы',
    aisulu_tote: 'Ою-өрнекті SaudaGo шопері', aisulu_hoodie: 'SaudaGo худиі',
    altai_badge: 'Алтай значогы', altai_mug: 'Алтай кружкасы', altai_cap: 'SaudaGo кепкасы', altai_tshirt: 'SaudaGo футболкасы',
  },
  claim: 'Алу', locked: p => `${p} ұпай`, requested: 'Жіберуге дайындалуда', sent: 'Жіберілді',
  addressLabel: 'Сыйлықты қайда жіберейік?', addressHint: 'Қала, көше, үй, пәтер', send: 'Жіберу', cancel: 'Болдырмау',
  errors: {
    not_enough_treats: 'Тағам жетпейді.', gift_locked: 'Бұл сыйлық әлі ашылмаған.',
    already_claimed: 'Бұл сыйлықты сұрап қойдыңыз.', address_required: 'Жеткізу мекенжайын жазыңыз.',
    generic: 'Қате кетті. Қайталап көріңіз.',
  },
  loading: 'Дастархан жайылуда…', empty: 'Әзірге тағам жоқ — төленген тапсырыстан кейін пайда болады.', shop: 'Сатып алуға',
};

export const BONUS_COPY: Record<Lang, BonusCopy> = { en: EN, ru: RU, kk: KK };
