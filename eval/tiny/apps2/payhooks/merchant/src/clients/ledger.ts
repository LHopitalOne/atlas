import axios from 'axios';

import { config } from '../config.ts';

export interface Balance {
  merchant_id: string;
  settled_cents: number;
  refunded_cents: number;
  balance_cents: number;
}

const ledger = axios.create({
  baseURL: config.ledgerUrl,
  timeout: 3000,
});

export async function fetchBalance(merchantId: string): Promise<Balance> {
  const { data } = await ledger.get<Balance>(`/balances/${encodeURIComponent(merchantId)}`);
  return data;
}
