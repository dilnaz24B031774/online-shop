import type { Lang } from './i18n.service';
import type { DeliveryTrackingStatus } from './delivery.service';

export interface TrackingCopy {
  title: string;
  order: string;
  back: string;
  trackLink: string;
  loading: string;
  refresh: string;
  refreshing: string;
  recenter: string;
  mapLabel: string;
  mapTitle: string;
  mapError: string;
  mapRetry: string;
  mapLoading: string;
  courier: string;
  destination: string;
  deliveryTo: string;
  latestEstimate: string;
  minutes: string;
  arriving: string;
  updated: string;
  noUpdate: string;
  sourceManual: string;
  sourceGps: string;
  stale: string;
  staleHint: string;
  autoRefresh: string;
  manualHint: string;
  progress: string;
  received: string;
  onTheWay: string;
  delivered: string;
  completed: string;
  current: string;
  upcoming: string;
  supportTitle: string;
  supportText: string;
  supportLink: string;
  call: string;
  errorTitle: string;
  errorText: string;
  notFound: string;
  sessionExpired: string;
  retry: string;
  states: Record<DeliveryTrackingStatus, { title: string; text: string }>;
}

export const TRACKING_COPY: Record<Lang, TrackingCopy> = {
  en: {
    title: 'Your delivery', order: 'Order', back: 'Back to my orders', trackLink: 'Track delivery',
    loading: 'Getting your delivery details…', refresh: 'Refresh', refreshing: 'Refreshing…', recenter: 'Recenter map',
    mapLabel: 'Map showing the latest reported courier location and delivery address', mapTitle: 'Delivery map',
    mapError: 'The map could not load. Your delivery details are still available.', mapRetry: 'Reload map', mapLoading: 'Loading the map…',
    courier: 'Courier', destination: 'Delivery address', deliveryTo: 'Delivering to',
    latestEstimate: 'Latest arrival estimate', minutes: 'min', arriving: 'Arriving soon', updated: 'Last location update', noUpdate: 'No location updates yet',
    sourceManual: 'Reported by the shop', sourceGps: 'Courier GPS', stale: 'Location update is delayed',
    staleHint: 'This location was reported more than 2 minutes ago. The courier may have moved since then.',
    autoRefresh: 'Updates refresh every 15 seconds while your order is on its way.',
    manualHint: 'The map shows the last location shared by the shop.',
    progress: 'Delivery progress', received: 'Order received', onTheWay: 'On its way', delivered: 'Delivered',
    completed: 'Completed', current: 'Current step', upcoming: 'Next step',
    supportTitle: 'A question about your delivery?', supportText: 'Our team can help with the address, timing or a delivery problem.', supportLink: 'Contact support', call: 'Call courier',
    errorTitle: 'We could not load this delivery', errorText: 'Please check your connection and try again. Your previous delivery details are shown below when available.',
    notFound: 'This order is not available. Open an order from your account to track it.', sessionExpired: 'Please sign in again to view your delivery.', retry: 'Try again',
    states: {
      unassigned: { title: 'Getting ready for delivery', text: 'A courier has not been assigned yet. Their details will appear here when the shop prepares your delivery.' },
      awaiting_shipment: { title: 'Your order is getting ready', text: 'Your courier is assigned. Their location will appear after the order is dispatched and a location is shared.' },
      awaiting_location: { title: 'Your order is on its way', text: 'We are waiting for the courier’s first location update. You can refresh this page or contact support.' },
      active: { title: 'Your order is on its way', text: 'Follow the latest reported location below. Arrival times are estimates and may change.' },
      stale: { title: 'Waiting for a fresh courier location', text: 'The courier is temporarily not sharing a recent location. We will update the map when a new GPS report arrives.' },
      delivered: { title: 'Delivered. Enjoy your order!', text: 'The shop has marked this order as delivered. Contact us if you need help with your purchase.' },
      cancelled: { title: 'This delivery was cancelled', text: 'There is no active delivery for this order. Our support team can help if you have a question.' },
    },
  },
  ru: {
    title: 'Ваша доставка', order: 'Заказ', back: 'К моим заказам', trackLink: 'Отследить доставку',
    loading: 'Загружаем информацию о доставке…', refresh: 'Обновить', refreshing: 'Обновляем…', recenter: 'Показать на карте',
    mapLabel: 'Карта с последним переданным местоположением курьера и адресом доставки', mapTitle: 'Карта доставки',
    mapError: 'Не удалось загрузить карту. Информация о доставке доступна ниже.', mapRetry: 'Загрузить карту снова', mapLoading: 'Загружаем карту…',
    courier: 'Курьер', destination: 'Адрес доставки', deliveryTo: 'Доставим по адресу',
    latestEstimate: 'Последняя оценка прибытия', minutes: 'мин', arriving: 'Скоро прибудет', updated: 'Местоположение обновлено', noUpdate: 'Местоположение ещё не передано',
    sourceManual: 'Передано магазином', sourceGps: 'GPS курьера', stale: 'Местоположение давно не обновлялось',
    staleHint: 'Эта точка передана более 2 минут назад. Курьер мог уже переместиться.',
    autoRefresh: 'Пока заказ в пути, проверяем обновления каждые 15 секунд.', manualHint: 'На карте — последнее местоположение, переданное магазином.',
    progress: 'Этапы доставки', received: 'Заказ принят', onTheWay: 'В пути', delivered: 'Доставлен',
    completed: 'Завершено', current: 'Текущий этап', upcoming: 'Следующий этап',
    supportTitle: 'Есть вопрос о доставке?', supportText: 'Поможем уточнить адрес, время или решить проблему с доставкой.', supportLink: 'Написать в поддержку', call: 'Позвонить курьеру',
    errorTitle: 'Не удалось загрузить доставку', errorText: 'Проверьте соединение и попробуйте снова. Если информация была загружена раньше, она показана ниже.',
    notFound: 'Этот заказ недоступен. Откройте заказ из своего аккаунта, чтобы отследить доставку.', sessionExpired: 'Войдите снова, чтобы посмотреть доставку.', retry: 'Попробовать снова',
    states: {
      unassigned: { title: 'Готовимся к доставке', text: 'Курьер ещё не назначен. Его данные появятся здесь, когда магазин подготовит доставку.' },
      awaiting_shipment: { title: 'Ваш заказ готовится', text: 'Курьер назначен. Местоположение появится после отправки заказа и передачи координат.' },
      awaiting_location: { title: 'Ваш заказ уже в пути', text: 'Ожидаем первое местоположение курьера. Можно обновить страницу или обратиться в поддержку.' },
      active: { title: 'Ваш заказ уже в пути', text: 'Следите за последним переданным местоположением. Время прибытия приблизительное и может меняться.' },
      stale: { title: 'Ожидаем новое местоположение', text: 'Курьер временно не передаёт геопозицию. Карта обновится, когда поступят новые GPS-данные.' },
      delivered: { title: 'Доставлено. Приятных покупок!', text: 'Магазин отметил заказ как доставленный. Обратитесь к нам, если нужна помощь с покупкой.' },
      cancelled: { title: 'Доставка отменена', text: 'Для этого заказа нет активной доставки. Поддержка поможет, если остались вопросы.' },
    },
  },
  kk: {
    title: 'Сіздің жеткізуіңіз', order: 'Тапсырыс', back: 'Тапсырыстарыма оралу', trackLink: 'Жеткізуді қадағалау',
    loading: 'Жеткізу туралы ақпарат жүктелуде…', refresh: 'Жаңарту', refreshing: 'Жаңартылуда…', recenter: 'Картада көрсету',
    mapLabel: 'Курьердің соңғы хабарланған орны мен жеткізу мекенжайы көрсетілген карта', mapTitle: 'Жеткізу картасы',
    mapError: 'Карта жүктелмеді. Жеткізу туралы ақпарат төменде қолжетімді.', mapRetry: 'Картаны қайта жүктеу', mapLoading: 'Карта жүктелуде…',
    courier: 'Курьер', destination: 'Жеткізу мекенжайы', deliveryTo: 'Жеткізілетін мекенжай',
    latestEstimate: 'Соңғы келу болжамы', minutes: 'мин', arriving: 'Жақында келеді', updated: 'Орны жаңартылды', noUpdate: 'Орны әлі жіберілмеген',
    sourceManual: 'Дүкен хабарлады', sourceGps: 'Курьердің GPS дерегі', stale: 'Курьердің орны біраз уақыт жаңартылмады',
    staleHint: 'Бұл орын 2 минуттан астам уақыт бұрын хабарланды. Курьер басқа жерге жылжыған болуы мүмкін.',
    autoRefresh: 'Тапсырыс жолда болғанда жаңартуларды әр 15 секунд сайын тексереміз.', manualHint: 'Картада дүкен хабарлаған соңғы орын көрсетілген.',
    progress: 'Жеткізу кезеңдері', received: 'Тапсырыс қабылданды', onTheWay: 'Жолда', delivered: 'Жеткізілді',
    completed: 'Аяқталды', current: 'Қазіргі кезең', upcoming: 'Келесі кезең',
    supportTitle: 'Жеткізу туралы сұрағыңыз бар ма?', supportText: 'Мекенжайды, уақытты нақтылауға немесе жеткізу мәселесін шешуге көмектесеміз.', supportLink: 'Қолдау қызметіне жазу', call: 'Курьерге қоңырау шалу',
    errorTitle: 'Жеткізу деректері жүктелмеді', errorText: 'Байланысты тексеріп, қайталап көріңіз. Бұрын жүктелген ақпарат болса, төменде көрсетіледі.',
    notFound: 'Бұл тапсырыс қолжетімсіз. Жеткізуді қадағалау үшін өз аккаунтыңыздағы тапсырысты ашыңыз.', sessionExpired: 'Жеткізуді көру үшін қайта кіріңіз.', retry: 'Қайталап көру',
    states: {
      unassigned: { title: 'Жеткізуге дайындалуда', text: 'Курьер әлі тағайындалмаған. Дүкен жеткізуді дайындағанда оның деректері осында пайда болады.' },
      awaiting_shipment: { title: 'Тапсырысыңыз дайындалуда', text: 'Курьер тағайындалды. Тапсырыс жөнелтіліп, координаттар жіберілгеннен кейін оның орны көрінеді.' },
      awaiting_location: { title: 'Тапсырысыңыз жолда', text: 'Курьердің алғашқы орын дерегін күтіп отырмыз. Бетті жаңартуға немесе қолдауға жазуға болады.' },
      active: { title: 'Тапсырысыңыз жолда', text: 'Соңғы хабарланған орынды қадағалаңыз. Келу уақыты шамамен берілген және өзгеруі мүмкін.' },
      stale: { title: 'Курьердің жаңа орнын күтеміз', text: 'Курьер уақытша геолокацияны жібермей жатыр. Жаңа GPS дерегі келгенде карта жаңартылады.' },
      delivered: { title: 'Жеткізілді. Сатып алуыңыз құтты болсын!', text: 'Дүкен тапсырысты жеткізілді деп белгіледі. Сатып алу бойынша көмек қажет болса, бізге жазыңыз.' },
      cancelled: { title: 'Жеткізу тоқтатылды', text: 'Бұл тапсырыс бойынша белсенді жеткізу жоқ. Сұрақтарыңыз болса, қолдау қызметі көмектеседі.' },
    },
  },
};
