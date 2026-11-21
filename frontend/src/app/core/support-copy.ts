import type { Lang } from './i18n.service';

export type SupportTopic = 'all' | 'account' | 'payment' | 'delivery';
interface Faq { topic: Exclude<SupportTopic, 'all'>; question: string; answer: string; }
interface SupportCopy {
  eyebrow: string; title: string; intro: string; contact: string; replyNote: string;
  faqTitle: string; searchLabel: string; searchPlaceholder: string; noResults: string; clear: string;
  topics: Record<SupportTopic, string>; faqs: Faq[];
  contactTitle: string; contactIntro: string; privacy: string; send: string;
  guestTitle: string; guestText: string; signIn: string;
  historyTitle: string; historyHint: string; emptyTitle: string; emptyText: string;
}

const COPY: Record<Lang, SupportCopy> = {
  en: {
    eyebrow: 'Sauda help center', title: 'A little help, right here.',
    intro: 'Find an answer, sort out an order, or send a question to our team.',
    contact: 'Contact support', replyNote: 'Your messages and our replies stay together in your account.',
    faqTitle: 'Good to know', searchLabel: 'Search help', searchPlaceholder: 'For example, payment or password',
    noResults: 'No matching answers. Try another search or send us a request.', clear: 'Clear search',
    topics: { all: 'All questions', account: 'Account & website', payment: 'Payment', delivery: 'Orders & delivery' },
    faqs: [
      { topic: 'account', question: 'I forgot my password. What should I do?', answer: 'Open “Forgot password” on the sign-in page and follow the recovery steps. If you previously linked Telegram in Settings, you can use it to recover access.' },
      { topic: 'account', question: 'Where can I change the language or appearance?', answer: 'Open Settings after signing in. Choose a light or dark appearance, an accent color, and the interface language. Appearance is remembered in this browser.' },
      { topic: 'payment', question: 'Why is my order still awaiting payment?', answer: 'A QR or bank-transfer order stays pending until payment is confirmed. Check the payment status and time remaining in your order. Cash on delivery is paid when the order is delivered.' },
      { topic: 'payment', question: 'My card was declined. How can I get help?', answer: 'Check the card details and the message on the payment screen. If the problem continues, send a request with the order number and the error text. Do not include your full card number or CVC.' },
      { topic: 'delivery', question: 'How do I check delivery to my city?', answer: 'Choose your city in the shop header. The product page shows the delivery estimate for that city. Your delivery address is selected at checkout.' },
      { topic: 'delivery', question: 'I need help with an order or a return.', answer: 'Open My orders to check the current status and available actions. For a return, delivery issue, or another question, send a request below and select the relevant order.' },
    ],
    contactTitle: 'Send us a message', contactIntro: 'A clear description helps us find the right solution.',
    privacy: 'Only you and authorized store staff can see your requests. Do not send passwords or full card details.',
    send: 'Send request', guestTitle: 'Let’s keep your conversation private.',
    guestText: 'Sign in to send a request, attach one of your orders, and see the team’s reply here.', signIn: 'Sign in to contact us',
    historyTitle: 'Your requests', historyHint: 'Questions and complaints, with their status and replies.',
    emptyTitle: 'A fresh start', emptyText: 'Your requests will appear here after you send your first message.',
  },
  ru: {
    eyebrow: 'Центр помощи Sauda', title: 'Поможем разобраться.',
    intro: 'Найдите ответ, уточните детали заказа или напишите нашей команде.',
    contact: 'Написать в поддержку', replyNote: 'Ваши сообщения и наши ответы сохраняются в личном кабинете.',
    faqTitle: 'Полезно знать', searchLabel: 'Поиск по вопросам', searchPlaceholder: 'Например, оплата или пароль',
    noResults: 'Подходящих ответов нет. Попробуйте другой запрос или напишите нам.', clear: 'Сбросить поиск',
    topics: { all: 'Все вопросы', account: 'Аккаунт и сайт', payment: 'Оплата', delivery: 'Заказы и доставка' },
    faqs: [
      { topic: 'account', question: 'Я забыл пароль. Что делать?', answer: 'Нажмите «Забыли пароль?» на странице входа и следуйте инструкциям. Если вы заранее привязали Telegram в настройках, его можно использовать для восстановления доступа.' },
      { topic: 'account', question: 'Где изменить язык или оформление?', answer: 'После входа откройте настройки. Выберите светлое или тёмное оформление, цвет акцента и язык интерфейса. Оформление запоминается в этом браузере.' },
      { topic: 'payment', question: 'Почему заказ всё ещё ожидает оплату?', answer: 'Заказ с оплатой по QR или переводом ожидает подтверждения платежа. Статус и оставшееся время оплаты указаны в заказе. При оплате наличными деньги передаются при доставке.' },
      { topic: 'payment', question: 'Платёж по карте отклонён. Как получить помощь?', answer: 'Проверьте данные карты и сообщение на экране оплаты. Если проблема повторяется, отправьте обращение с номером заказа и текстом ошибки. Не указывайте полный номер карты и CVC.' },
      { topic: 'delivery', question: 'Как узнать о доставке в мой город?', answer: 'Выберите город в шапке магазина. На странице товара появится ориентировочный срок доставки для этого города. Адрес доставки выбирается при оформлении заказа.' },
      { topic: 'delivery', question: 'Нужна помощь с заказом или возвратом.', answer: 'В разделе «Мои заказы» можно проверить статус и доступные действия. По вопросам возврата, доставки и другим сложностям напишите нам ниже и выберите нужный заказ.' },
    ],
    contactTitle: 'Напишите нам', contactIntro: 'Подробное описание поможет быстрее разобраться в вопросе.',
    privacy: 'Обращения видны только вам и уполномоченным сотрудникам магазина. Не отправляйте пароли и полные данные карты.',
    send: 'Отправить обращение', guestTitle: 'Сохраним переписку личной.',
    guestText: 'Войдите, чтобы отправить обращение, выбрать свой заказ и увидеть ответ команды здесь.', signIn: 'Войти и написать',
    historyTitle: 'Ваши обращения', historyHint: 'Вопросы и жалобы, их статусы и ответы команды.',
    emptyTitle: 'Пока всё спокойно', emptyText: 'Здесь появятся ваши обращения после первого сообщения.',
  },
  kk: {
    eyebrow: 'Sauda көмек орталығы', title: 'Бірге шешім табамыз.',
    intro: 'Жауап табыңыз, тапсырысты нақтылаңыз немесе біздің командаға жазыңыз.',
    contact: 'Қолдауға жазу', replyNote: 'Хабарламаларыңыз бен жауаптар жеке кабинетте сақталады.',
    faqTitle: 'Білгеніңіз жөн', searchLabel: 'Сұрақтарды іздеу', searchPlaceholder: 'Мысалы, төлем немесе құпиясөз',
    noResults: 'Сәйкес жауап табылмады. Басқа сөзбен іздеңіз немесе бізге жазыңыз.', clear: 'Іздеуді тазалау',
    topics: { all: 'Барлық сұрақтар', account: 'Аккаунт және сайт', payment: 'Төлем', delivery: 'Тапсырыс пен жеткізу' },
    faqs: [
      { topic: 'account', question: 'Құпиясөзді ұмыттым. Не істеу керек?', answer: 'Кіру бетінде «Құпиясөзді ұмыттыңыз ба?» түймесін басып, нұсқауларды орындаңыз. Егер баптауларда Telegram алдын ала байланыстырылса, сол арқылы қолжетімділікті қалпына келтіруге болады.' },
      { topic: 'account', question: 'Тіл мен безендіруді қайдан өзгертемін?', answer: 'Жүйеге кіргеннен кейін баптауларды ашыңыз. Ашық не қараңғы безендіруді, негізгі түс пен интерфейс тілін таңдаңыз. Безендіру осы браузерде сақталады.' },
      { topic: 'payment', question: 'Неліктен тапсырыс әлі төлемді күтіп тұр?', answer: 'QR немесе аударым арқылы төленетін тапсырыс төлем расталғанша күтілуде болады. Төлем мәртебесі мен қалған уақыт тапсырыста көрсетіледі. Қолма-қол төлем жеткізу кезінде жасалады.' },
      { topic: 'payment', question: 'Карта төлемі қабылданбады. Қалай көмек аламын?', answer: 'Карта деректері мен төлем экранындағы хабарламаны тексеріңіз. Мәселе қайталанса, тапсырыс нөмірі мен қате мәтінін жіберіңіз. Картаның толық нөмірі мен CVC кодын көрсетпеңіз.' },
      { topic: 'delivery', question: 'Қалама жеткізу туралы қалай білемін?', answer: 'Дүкеннің жоғарғы бөлігінен қалаңызды таңдаңыз. Тауар бетінде осы қалаға жеткізу мерзімі көрсетіледі. Жеткізу мекенжайы тапсырысты рәсімдегенде таңдалады.' },
      { topic: 'delivery', question: 'Тапсырыс немесе қайтарым бойынша көмек керек.', answer: '«Менің тапсырыстарым» бөлімінен мәртебе мен қолжетімді әрекеттерді тексеріңіз. Қайтарым, жеткізу немесе басқа сұрақ бойынша төменде жазып, тиісті тапсырысты таңдаңыз.' },
    ],
    contactTitle: 'Бізге жазыңыз', contactIntro: 'Толық сипаттама мәселені түсінуге көмектеседі.',
    privacy: 'Өтініштерді тек сіз және дүкеннің уәкілетті қызметкерлері көреді. Құпиясөздер мен картаның толық деректерін жібермеңіз.',
    send: 'Өтініш жіберу', guestTitle: 'Хат алмасу құпия сақталады.',
    guestText: 'Өтініш жіберу, өз тапсырысыңызды таңдау және команданың жауабын көру үшін жүйеге кіріңіз.', signIn: 'Кіру және жазу',
    historyTitle: 'Сіздің өтініштеріңіз', historyHint: 'Сұрақтар мен шағымдар, олардың мәртебелері және жауаптар.',
    emptyTitle: 'Әзірге бәрі тыныш', emptyText: 'Алғашқы хабарлама жіберілгеннен кейін өтініштеріңіз осында көрсетіледі.',
  },
};

export const supportCopy = (language: Lang): SupportCopy => COPY[language];
