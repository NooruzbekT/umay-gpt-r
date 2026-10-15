export type Lang = "ru" | "kk" | "en";

export type Product = {
  id: string;
  title: string;
  emoji: string;
  category: string;
  price: number;
  old_price: number | null;
  rating: number;
  reviews: number;
  colors: string[];
  installment_24: number;
  delivery_days: number;
  source: string;
  in_stock: boolean;
  image?: string | null;
  url?: string | null;
  qty?: number;
};

export type Artifact =
  | { kind: "PRODUCT_LIST"; products: Product[] }
  | { kind: "BUNDLE"; products: Product[]; total: number; budget: number }
  | { kind: "COMPARISON"; products: Product[] }
  | { kind: "CART"; items: Product[]; total: number; installment_24: number };

export type Cart = { items: Product[]; total: number; installment_24: number };

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  artifacts: Artifact[];
  status?: string;
  suggestions?: string[];
  image?: string;
  error?: string;
  pending?: boolean;
};

export type ChatMeta = { id: string; title: string; updatedAt: number };

export type StreamEvent =
  | { type: "session"; session_id: string; agent: string }
  | { type: "status"; text: string }
  | { type: "text"; delta: string }
  | { type: "artifact"; artifact: Artifact }
  | { type: "suggestions"; items: string[] }
  | { type: "done" };
