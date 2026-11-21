import type { Lang } from './i18n.service';
import type { Accent } from './theme.service';

interface AppearanceCopy {
  title: string;
  subtitle: string;
  theme: string;
  light: string;
  dark: string;
  lightHint: string;
  darkHint: string;
  accent: string;
  accents: Record<Accent, string>;
  language: string;
  languageHint: string;
  deviceHint: string;
  saved: string;
  support: string;
}

const COPY: Record<Lang, AppearanceCopy> = {
  en: {
    title: 'Make Sauda yours', subtitle: 'Choose a comfortable look and your preferred language.',
    theme: 'Appearance', light: 'Light', dark: 'Dark', lightHint: 'Bright and familiar', darkHint: 'Comfort for evening browsing',
    accent: 'Accent color', accents: { green: 'Forest', blue: 'Ocean', violet: 'Iris' },
    language: 'Interface language', languageHint: 'Menus and messages change immediately.',
    deviceHint: 'Appearance is saved in this browser.', saved: 'Preferences updated', support: 'Help & support',
  },
  ru: {
    title: 'Sauda в вашем стиле', subtitle: 'Выберите удобное оформление и язык интерфейса.',
    theme: 'Оформление', light: 'Светлое', dark: 'Тёмное', lightHint: 'Светлый и привычный интерфейс', darkHint: 'Для комфортного просмотра вечером',
    accent: 'Цвет акцента', accents: { green: 'Лес', blue: 'Океан', violet: 'Ирис' },
    language: 'Язык интерфейса', languageHint: 'Меню и сообщения изменятся сразу.',
    deviceHint: 'Оформление сохраняется в этом браузере.', saved: 'Настройки обновлены', support: 'Помощь и поддержка',
  },
  kk: {
    title: 'Sauda — өз стиліңізде', subtitle: 'Ыңғайлы безендіру мен интерфейс тілін таңдаңыз.',
    theme: 'Безендіру', light: 'Ашық', dark: 'Қараңғы', lightHint: 'Жарық әрі таныс интерфейс', darkHint: 'Кешкі уақытта қарауға ыңғайлы',
    accent: 'Негізгі түс', accents: { green: 'Орман', blue: 'Мұхит', violet: 'Ирис' },
    language: 'Интерфейс тілі', languageHint: 'Мәзір мен хабарламалар бірден өзгереді.',
    deviceHint: 'Безендіру осы браузерде сақталады.', saved: 'Баптаулар жаңартылды', support: 'Көмек және қолдау',
  },
};

export const appearanceCopy = (language: Lang): AppearanceCopy => COPY[language];
