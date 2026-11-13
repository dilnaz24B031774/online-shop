"""
Simple shop assistant (rule-based, works offline, no external AI).

It understands the message by keywords in English, Russian and Kazakh:
  - questions about delivery, payment, refunds, contacts, the customer's order
  - product requests: category words + price limits ("headphones under 100",
    "кроссовки до 120", "сыйлық 50 дейін")
and answers with text + matching products from the database.
"""
import re
from decimal import Decimal

from django.db.models import Avg, Count, F, Q, Sum

from .models import Order, Product

# ------------------------------------------------------------------ keywords
INTENTS = {
    "greeting": ["hello", "hi ", "hey", "привет", "здравств", "добрый", "сәлем", "салем", "сәлеметсіз"],
    "thanks": ["thank", "спасибо", "благодар", "рахмет", "рақмет"],
    "delivery": ["deliver", "shipping", "ship ", "доставк", "достав", "привез", "жеткіз", "жеткізу"],
    "payment": ["pay", "payment", "card", "cash", "оплат", "карт", "налич", "төле", "төлем", "қолма-қол"],
    "refund": ["refund", "return", "cancel", "возврат", "вернут", "верну", "отмен", "қайтар", "бас тарт"],
    "order": ["my order", "where is", "order status", "мой заказ", "где заказ", "статус заказ", "где мой",
              "тапсырысым", "менің тапсырыс", "тапсырыс қайда"],
    "contact": ["contact", "phone", "support", "operator", "поддержк", "контакт", "телефон", "оператор",
                "байланыс", "қолдау"],
    "gift": ["gift", "present", "подар", "сыйлық", "сыйға"],
}

CATEGORY_WORDS = {
    "Electronics": ["phone", "smartphone", "iphone", "samsung", "laptop", "notebook pc", "macbook", "tablet", "ipad",
                    "headphone", "earphone", "airpods", "speaker", "gadget", "electronic", "mouse", "cable",
                    "телефон", "смартфон", "ноутбук", "планшет", "наушник", "колонк", "гаджет", "электрон",
                    "мыш", "кабел", "құлаққап", "тінтуір", "кабель"],
    "Fashion": ["dress", "shirt", "t-shirt", "clothes", "fashion", "платье", "рубашк", "футболк", "одежд",
                "киім", "көйлек", "жейде"],
    "Shoes": ["shoe", "sneaker", "trainer", "heel", "кроссовк", "туфл", "обув", "кед", "аяқ киім", "кроссовка"],
    "Accessories": ["watch", "sunglass", "glasses", "bag", "backpack", "accessor", "часы", "очки", "сумк",
                    "рюкзак", "аксессуар", "сағат", "көзілдірік", "сөмке"],
    "Beauty": ["perfume", "fragrance", "lipstick", "makeup", "beauty", "cosmetic", "парфюм", "духи", "аромат",
               "помад", "косметик", "красот", "иіс", "сұлулық", "далап"],
    "Home": ["home", "kitchen", "lamp", "furniture", "chair", "plant", "blender", "для дома", "кухн", "ламп",
             "мебел", "кресл", "растен", "блендер", "үй", "ас үй", "шам", "кресло", "өсімдік"],
    "Sports": ["sport", "ball", "tennis", "football", "basketball", "volleyball", "спорт", "мяч", "теннис",
               "футбол", "баскетбол", "волейбол", "доп"],
    "Stationery": ["stationery", "pen", "notebook", "канц", "тетрад", "ручк", "кеңсе", "дәптер", "қалам"],
    "Books": ["book", "книг", "учебник", "кітап", "оқулық"],
}

MAX_WORDS = ["under", "below", "less than", "up to", "cheaper than", "до", "дешевле", "не дороже",
             "дейін", "арзан", "аспайтын"]
MIN_WORDS = ["over", "more than", "from", "above", "от", "дороже", "больше", "бастап", "жоғары"]
CHEAP_WORDS = ["cheap", "budget", "дешев", "недорог", "бюджет", "арзан"]

STOP = {"the", "and", "for", "with", "что", "для", "как", "мне", "под", "это", "есть", "хочу", "нужен",
        "нужна", "нужно", "покажи", "найди", "show", "find", "want", "need", "маған", "керек", "көрсет",
        "бар", "ма", "ме", "па", "пе", "under", "до", "дейін", "price", "цена", "баға"}

# ------------------------------------------------------------------ answers
TEXT = {
    "greeting": {
        "en": "Hi! I'm the Sauda assistant. I can find products (for example \"headphones under $150\") and answer questions about delivery, payment and refunds.",
        "ru": "Привет! Я помощник Sauda. Могу подобрать товары (например, «наушники до 150$») и ответить на вопросы о доставке, оплате и возврате.",
        "kk": "Сәлем! Мен Sauda көмекшісімін. Тауар таңдап бере аламын (мысалы, «құлаққап 150$ дейін») және жеткізу, төлем, қайтару туралы сұрақтарға жауап беремін.",
    },
    "thanks": {
        "en": "You're welcome! Ask me anything else about the shop.",
        "ru": "Пожалуйста! Спрашивайте, если нужно что-то ещё.",
        "kk": "Оқасы жоқ! Тағы сұрақтарыңыз болса, сұраңыз.",
    },
    "delivery": {
        "en": "We deliver across Kazakhstan: Almaty, Astana, Shymkent and other cities. You choose the address at checkout, and you can save several addresses (home, work).",
        "ru": "Доставляем по всему Казахстану: Алматы, Астана, Шымкент и другие города. Адрес выбирается при оформлении заказа, можно сохранить несколько адресов (дом, работа).",
        "kk": "Қазақстан бойынша жеткіземіз: Алматы, Астана, Шымкент және басқа қалалар. Мекенжайды тапсырыс беру кезінде таңдайсыз, бірнеше мекенжай сақтауға болады (үй, жұмыс).",
    },
    "payment": {
        "en": "You can pay by card, by bank transfer or in cash on delivery. We never store card numbers.",
        "ru": "Оплатить можно картой, банковским переводом или наличными при получении. Номера карт мы не храним.",
        "kk": "Картамен, банк аударымымен немесе алған кезде қолма-қол төлеуге болады. Карта нөмірлерін сақтамаймыз.",
    },
    "refund": {
        "en": "You can cancel an order on the \"My orders\" page until it is shipped. The money is refunded and the products go back to stock automatically.",
        "ru": "Заказ можно отменить на странице «Мои заказы», пока он не отправлен. Деньги вернутся, а товары автоматически вернутся на склад.",
        "kk": "Тапсырыс жіберілгенге дейін «Тапсырыстарым» бетінде одан бас тартуға болады. Ақша қайтарылады, тауарлар қоймаға автоматты түрде оралады.",
    },
    "contact": {
        "en": "Support works every day from 9:00 to 21:00: +7 700 000 00 00, hello@sauda.kz.",
        "ru": "Поддержка работает каждый день с 9:00 до 21:00: +7 700 000 00 00, hello@sauda.kz.",
        "kk": "Қолдау күн сайын 9:00-ден 21:00-ге дейін жұмыс істейді: +7 700 000 00 00, hello@sauda.kz.",
    },
    "order_login": {
        "en": "Please sign in, and I will tell you the status of your orders.",
        "ru": "Войдите в аккаунт, и я подскажу статус ваших заказов.",
        "kk": "Аккаунтқа кіріңіз, мен тапсырыстарыңыздың күйін айтамын.",
    },
    "order_none": {
        "en": "You have no orders yet. Shall I help you choose something?",
        "ru": "У вас пока нет заказов. Помочь что-нибудь выбрать?",
        "kk": "Сізде әзірге тапсырыс жоқ. Бірдеңе таңдауға көмектесейін бе?",
    },
    "order_status": {
        "en": "Your last order #{id} is {status}, total ${total}. All orders are on the \"My orders\" page.",
        "ru": "Ваш последний заказ №{id}: {status}, сумма ${total}. Все заказы — на странице «Мои заказы».",
        "kk": "Соңғы №{id} тапсырысыңыз: {status}, сомасы ${total}. Барлық тапсырыс «Тапсырыстарым» бетінде.",
    },
    "found": {
        "en": "Here is what I found{price}:",
        "ru": "Вот что я нашёл{price}:",
        "kk": "Мынаны таптым{price}:",
    },
    "gift": {
        "en": "Popular gift ideas{price}:",
        "ru": "Популярные идеи для подарка{price}:",
        "kk": "Сыйлыққа танымал идеялар{price}:",
    },
    "not_found": {
        "en": "I couldn't find matching products. Try another word, for example \"sneakers\", \"perfume\" or \"laptop under 1500\".",
        "ru": "Не нашёл подходящих товаров. Попробуйте другое слово, например «кроссовки», «духи» или «ноутбук до 1500».",
        "kk": "Сәйкес тауар таппадым. Басқа сөзбен көріңіз, мысалы «кроссовка», «иіссу» немесе «ноутбук 1500 дейін».",
    },
    "closest": {
        "en": "Nothing under ${n}, but here are the closest options:",
        "ru": "До {n}$ ничего нет, но вот самые близкие варианты:",
        "kk": "{n}$ дейін ештеңе жоқ, бірақ ең жақын нұсқалар мыналар:",
    },
    "under": {"en": " under ${n}", "ru": " до {n}$", "kk": " {n}$ дейін"},
    "over": {"en": " over ${n}", "ru": " от {n}$", "kk": " {n}$ бастап"},
}

STATUS = {
    "en": {"pending": "pending", "paid": "paid", "shipped": "on the way", "delivered": "delivered", "cancelled": "cancelled"},
    "ru": {"pending": "ожидает оплаты", "paid": "оплачен", "shipped": "в пути", "delivered": "доставлен", "cancelled": "отменён"},
    "kk": {"pending": "төлемді күтуде", "paid": "төленді", "shipped": "жолда", "delivered": "жеткізілді", "cancelled": "бас тартылды"},
}

SUGGESTIONS = {
    "en": ["Headphones under $150", "Gift ideas", "Sneakers", "How does delivery work?", "How to get a refund?", "Where is my order?"],
    "ru": ["Наушники до 150$", "Что подарить?", "Кроссовки", "Как работает доставка?", "Как вернуть заказ?", "Где мой заказ?"],
    "kk": ["Құлаққап 150$ дейін", "Не сыйлауға болады?", "Кроссовка", "Жеткізу қалай?", "Тапсырысты қалай қайтарамын?", "Менің тапсырысым қайда?"],
}


def _has(text, words):
    return any(w in text for w in words)


def _price_limits(text):
    """Finds "under 100" / "до 100" / "100 дейін" / "from 50"."""
    max_price = min_price = None
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:\$|usd|долл|тенге|тг)?", text):
        value = Decimal(m.group(1).replace(",", "."))
        before = text[max(0, m.start() - 14):m.start()]
        after = text[m.end():m.end() + 12]
        if _has(before, MAX_WORDS) or _has(after, ["дейін", "дейінгі", "или дешевле", "or less"]):
            max_price = value
        elif _has(before, MIN_WORDS) or _has(after, ["бастап", "and more", "и дороже"]):
            min_price = value
        elif max_price is None and min_price is None and len(m.group(1)) >= 2:
            max_price = value          # "наушники 100$" -> treat as a budget
    return min_price, max_price


# precise topics: words in the question -> words in product names
TOPICS = [
    (["headphone", "earphone", "airpods", "наушник", "құлаққап"], ["headp", "airpod", "beats", "earph", "наушн", "құлақ"]),
    (["smartphone", "phone", "телефон", "смартфон"], ["iphone", "galaxy s", "realme", "смартф"]),
    (["laptop", "ноутбук", "macbook"], ["macbook", "zenbook", "ноутб"]),
    (["tablet", "ipad", "планшет"], ["ipad", "tab s", "планш"]),
    (["watch", "часы", "сағат"], ["watch", "часы", "сағат", "longines"]),
    (["sneaker", "trainer", "кроссовк", "кеды", "кед "], ["jordan", "puma", "sneak", "кросс", "кед"]),
    (["perfume", "fragrance", "духи", "парфюм", "аромат", "иіссу"], ["ck one", "dior", "gucci"]),
    (["dress", "платье", "көйлек"], ["dress", "frock", "gown", "платье", "көйлек"]),
    (["shirt", "рубашк", "футболк", "жейде"], ["shirt", "рубаш", "футбол", "жейде"]),
    (["bag", "backpack", "сумк", "рюкзак", "сөмке"], ["bag", "backpack", "сумк", "рюкзак", "сөмке"]),
    (["sunglass", "glasses", "очки", "көзілдірік"], ["glasses", "очки", "көзілдірік"]),
    (["ball", "мяч", "доп "], ["ball", "мяч", "доп"]),
    (["lamp", "ламп", "шам"], ["lamp", "ламп", "шам"]),
]


def _name_filter(stems):
    q = Q()
    for st in stems:
        q |= Q(name_en__icontains=st) | Q(name_ru__icontains=st) | Q(name_kk__icontains=st)
    return q


def _find_products(text, min_price, max_price, gift=False):
    qs = (Product.objects.filter(is_active=True, stock_quantity__gt=0).select_related("category")
          .annotate(avg_rating=Avg("reviews__rating"), review_count=Count("reviews", distinct=True),
                    sold=Sum("order_items__quantity")))
    if min_price is not None:
        qs = qs.filter(price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(price__lte=max_price)

    topic_stems = [st for words, stems in TOPICS if _has(text, words) for st in stems]
    cats = [c for c, words in CATEGORY_WORDS.items() if _has(text, words)]
    tokens = [t for t in re.findall(r"[a-zа-яёәғқңөұүһі\-]{3,}", text) if t not in STOP]

    if topic_stems:                          # 1) exact topic: "headphones", "sneakers" ...
        qs = qs.filter(_name_filter(topic_stems))
    elif cats:                               # 2) a whole category: "electronics", "for home" ...
        qs = qs.filter(category__name_en__in=cats)
    elif tokens and not gift:                # 3) any other word: brand or product name
        word_q = _name_filter([t[:5] for t in tokens])
        for t in tokens:
            word_q |= Q(brand__icontains=t)
        qs = qs.filter(word_q)
    elif not gift and min_price is None and max_price is None:
        return []

    if gift:
        order = [F("avg_rating").desc(nulls_last=True), F("sold").desc(nulls_last=True), "price"]
    elif max_price is not None or _has(text, CHEAP_WORDS):
        order = ["price"]
    else:
        order = [F("sold").desc(nulls_last=True), F("avg_rating").desc(nulls_last=True), "-id"]
    return list(qs.order_by(*order)[:4])


def reply(message: str, lang: str = "en", user=None) -> dict:
    lang = lang if lang in ("en", "ru", "kk") else "en"
    text = " " + (message or "").lower().strip() + " "
    answer = {"text": "", "products": [], "suggestions": SUGGESTIONS[lang][:4]}

    if not message or not message.strip():
        answer["text"] = TEXT["greeting"][lang]
        return answer

    # questions about the customer's own order
    if _has(text, INTENTS["order"]):
        if not user:
            answer["text"] = TEXT["order_login"][lang]
        else:
            last = Order.objects.filter(user=user).order_by("-created_at").first()
            answer["text"] = (TEXT["order_none"][lang] if not last else TEXT["order_status"][lang].format(
                id=last.pk, status=STATUS[lang][last.status], total=last.total_amount))
        return answer

    min_price, max_price = _price_limits(text)
    gift = _has(text, INTENTS["gift"])
    wants_products = gift or min_price is not None or max_price is not None or any(
        _has(text, w) for w in CATEGORY_WORDS.values())

    # FAQ answers (only when the message is not a product request)
    if not wants_products:
        for intent in ("refund", "delivery", "payment", "contact", "thanks", "greeting"):
            if _has(text, INTENTS[intent]):
                answer["text"] = TEXT[intent][lang]
                return answer

    products = _find_products(text, min_price, max_price, gift=gift)
    if not products and max_price is not None:
        # nothing in the budget -> show the cheapest matching products above it
        closest = _find_products(text.replace(m_str := f"{max_price:g}", ""), min_price, None, gift=gift)
        closest = sorted(closest, key=lambda p: p.price)[:3]
        if closest:
            answer["text"] = TEXT["closest"][lang].format(n=m_str)
            answer["products"] = closest
            return answer
    if products:
        price = ""
        if max_price is not None:
            price = TEXT["under"][lang].format(n=f"{max_price:g}")
        elif min_price is not None:
            price = TEXT["over"][lang].format(n=f"{min_price:g}")
        answer["text"] = TEXT["gift" if gift else "found"][lang].format(price=price)
        answer["products"] = products
    else:
        answer["text"] = TEXT["not_found"][lang]
        answer["suggestions"] = SUGGESTIONS[lang][:3]
    return answer
