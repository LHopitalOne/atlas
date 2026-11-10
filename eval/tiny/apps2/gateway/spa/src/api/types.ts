export interface User {
  id: number;
  name: string;
  email: string;
  verified: boolean;
}

export interface WishlistItem {
  sku: string;
  note: string;
}

export interface LineItem {
  sku: string;
  qty: number;
  price_usd: number;
}

export interface Order {
  id: number;
  buyer_id: number;
  currency: string;
  total: number;
  items: LineItem[];
}

export interface Dashboard {
  user: User;
  orders: Order[];
  stats: { orderCount: number; spentUsd: number };
}
