export const config = {
  restaurant: {
    baseUrl: process.env.RESTAURANT_API_URL ?? "http://localhost:8000",
    defaultRestaurantId: Number(process.env.DEFAULT_RESTAURANT_ID ?? 1),
    endpoints: {
      menu: "/menus",
      orders: "/orders",
    },
  },
  pollIntervalMs: 300,
} as const;
