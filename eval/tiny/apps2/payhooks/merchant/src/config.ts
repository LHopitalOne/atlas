export const config = {
  port: Number(process.env.PORT ?? 46020),
  publicUrl: process.env.PUBLIC_URL ?? 'http://127.0.0.1:46020',
  providerUrl: process.env.PROVIDER_URL ?? 'http://127.0.0.1:46010',
  ledgerUrl: process.env.LEDGER_URL ?? 'http://127.0.0.1:46030',
  merchantName: process.env.MERCHANT_NAME ?? 'payhooks-demo-shop',
};
