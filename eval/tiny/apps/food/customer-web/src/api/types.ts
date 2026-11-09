export interface MenuItem {
  sku: string;
  name: string;
  price_cents: number;
}

export interface Menu {
  restaurant_id: number;
  items: MenuItem[];
}

export interface Order {
  id: number;
  restaurant_id: number;
  items: string[];
  address: string;
  status: string;
  history: string[];
}

export interface NewOrder {
  restaurant_id: number;
  items: string[];
  address: string;
}
