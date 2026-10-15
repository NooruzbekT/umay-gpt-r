import type { Lang } from "./types";

export const LANGS: { id: Lang; label: string; speech: string }[] = [
  { id: "ru", label: "Рус", speech: "ru-RU" },
  { id: "kk", label: "Қаз", speech: "kk-KZ" },
  { id: "en", label: "Eng", speech: "en-US" },
];

type Dict = Record<string, string | string[]>;

const ru: Dict = {
  newChat: "Новый чат",
  chats: "Чаты",
  noChats: "Здесь появятся ваши диалоги",
  cart: "Корзина",
  hello: "Что ищем сегодня?",
  sub: "Опишите покупку своими словами, с бюджетом — подберу из каталога Umay, сравню и положу в корзину.",
  placeholder: "Например: тёплая куртка на осень до 20 000 ₸",
  send: "Отправить",
  voice: "Голосовой ввод",
  photo: "Найти по фото",
  listening: "Слушаю…",
  disclaimer: "Umay GPT может ошибаться — сверяйте цену и наличие в карточке товара",
  starters: [
    "Тёплая куртка на осень до 20 000 ₸",
    "Обустроить детскую комнату до 100 000 ₸",
    "Подарок маме до 10 000 ₸",
    "Беспроводные наушники",
  ],
  addToCart: "В корзину",
  added: "В корзине",
  perMonth: "/мес",
  installment: "0-0-24",
  delivery: "дн. доставка",
  compare: "Сравнение",
  price: "Цена",
  rating: "Рейтинг",
  deliveryRow: "Доставка",
  installmentRow: "Рассрочка 24 мес",
  sourceRow: "Магазин",
  bundle: "Набор под бюджет",
  of: "из",
  left: "остаётся",
  cartEmpty: "Корзина пуста. Попросите Umay GPT подобрать что-нибудь — товары можно класть прямо из чата.",
  total: "Итого",
  checkout: "Оформить заказ",
  remove: "Убрать",
  errorNet: "Не удалось связаться с сервером. Проверьте, что бэкенд запущен, и отправьте ещё раз.",
  errorRate: "Слишком много запросов подряд. Подождите минуту и отправьте снова.",
  retry: "Повторить",
  photoFound: "По фото: товары цвета",
  days: "дн.",
};

const kk: Dict = {
  ...ru,
  newChat: "Жаңа чат",
  chats: "Чаттар",
  noChats: "Мұнда сіздің диалогтарыңыз пайда болады",
  cart: "Себет",
  hello: "Бүгін не іздейміз?",
  sub: "Сатып алатыныңызды өз сөзіңізбен, бюджетімен жазыңыз — Umay каталогынан таңдап, салыстырып, себетке салып беремін.",
  placeholder: "Мысалы: күзге жылы күрте 20 000 ₸ дейін",
  send: "Жіберу",
  voice: "Дауыспен енгізу",
  photo: "Фото бойынша іздеу",
  listening: "Тыңдап тұрмын…",
  disclaimer: "Umay GPT қателесуі мүмкін — баға мен қолжетімділікті тауар карточкасынан тексеріңіз",
  starters: ["Күзге жылы күрте 20 000 ₸ дейін", "Балалар бөлмесі 100 000 ₸ дейін", "Анама сыйлық 10 000 ₸ дейін", "Сымсыз құлаққап"],
  addToCart: "Себетке",
  added: "Себетте",
  perMonth: "/ай",
  delivery: "күн жеткізу",
  compare: "Салыстыру",
  price: "Баға",
  rating: "Рейтинг",
  deliveryRow: "Жеткізу",
  installmentRow: "24 айға бөліп төлеу",
  sourceRow: "Дүкен",
  bundle: "Бюджетке жиынтық",
  of: "ішінен",
  left: "қалады",
  cartEmpty: "Себет бос. Umay GPT-ден бірдеңе таңдауды сұраңыз — тауарларды чаттан тікелей салуға болады.",
  total: "Барлығы",
  checkout: "Тапсырыс беру",
  remove: "Алып тастау",
  errorNet: "Серверге қосылу мүмкін болмады. Бэкенд іске қосылғанын тексеріп, қайта жіберіңіз.",
  errorRate: "Сұраныстар тым көп. Бір минут күтіп, қайта жіберіңіз.",
  retry: "Қайталау",
  photoFound: "Фото бойынша: түсі",
  days: "күн",
};

const en: Dict = {
  ...ru,
  newChat: "New chat",
  chats: "Chats",
  noChats: "Your conversations will show up here",
  cart: "Cart",
  hello: "What are we shopping for?",
  sub: "Describe what you need in your own words, budget included — I'll pick from the Umay catalog, compare and add to your cart.",
  placeholder: "e.g. warm autumn jacket under 20,000 ₸",
  send: "Send",
  voice: "Voice input",
  photo: "Search by photo",
  listening: "Listening…",
  disclaimer: "Umay GPT can make mistakes — check price and stock on the product page",
  starters: ["Warm autumn jacket under 20,000 ₸", "Kids' room setup under 100,000 ₸", "Gift for mom under 10,000 ₸", "Wireless headphones"],
  addToCart: "Add to cart",
  added: "In cart",
  perMonth: "/mo",
  delivery: "days delivery",
  compare: "Comparison",
  price: "Price",
  rating: "Rating",
  deliveryRow: "Delivery",
  installmentRow: "24-month installments",
  sourceRow: "Store",
  bundle: "Bundle within budget",
  of: "of",
  left: "left",
  cartEmpty: "Your cart is empty. Ask Umay GPT to find something — you can add items right from the chat.",
  total: "Total",
  checkout: "Check out",
  remove: "Remove",
  errorNet: "Couldn't reach the server. Make sure the backend is running and send again.",
  errorRate: "Too many requests in a row. Wait a minute and send again.",
  retry: "Retry",
  photoFound: "From your photo: items in",
  days: "days",
};

const DICTS: Record<Lang, Dict> = { ru, kk, en };

export function t(lang: Lang, key: string): string {
  const v = DICTS[lang][key];
  return Array.isArray(v) ? v.join(", ") : v ?? key;
}

export function tl(lang: Lang, key: string): string[] {
  const v = DICTS[lang][key];
  return Array.isArray(v) ? v : [String(v)];
}
