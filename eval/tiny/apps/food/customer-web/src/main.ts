import { config } from "./config";
import { fetchMenu, getOrder, placeOrder } from "./api/restaurant";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function trackOrder(orderId: number, until: string, attempts = 40): Promise<void> {
  for (let i = 0; i < attempts; i++) {
    const order = await getOrder(orderId);
    console.log(`order ${orderId}: ${order.status}`);
    if (order.status === until) return;
    await sleep(config.pollIntervalMs);
  }
  throw new Error(`order ${orderId} never reached ${until}`);
}

async function main(): Promise<void> {
  const restaurantId = config.restaurant.defaultRestaurantId;
  const menu = await fetchMenu(restaurantId);
  console.log(`menu: ${menu.items.map((i) => i.name).join(", ")}`);

  const order = await placeOrder({
    restaurant_id: restaurantId,
    items: menu.items.slice(0, 2).map((i) => i.sku),
    address: "12 Baker St",
  });
  console.log(`placed order ${order.id}`);

  const until = process.argv[2] ?? "delivered";
  await trackOrder(order.id, until);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
