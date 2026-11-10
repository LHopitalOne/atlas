export const config = {
  port: Number(process.env.PORT ?? 43010),
  usersUrl: process.env.USERS_URL ?? 'http://127.0.0.1:43020',
  ordersUrl: process.env.ORDERS_URL ?? 'http://127.0.0.1:43030',
};
