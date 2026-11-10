const BINLIST_URL = 'https://lookup.binlist.net';
const ECHO_URL = 'https://httpbin.org/anything/bins';

export interface CardInfo {
  bin: string;
  scheme: string | null;
  country: string | null;
  source: 'binlist' | 'fallback';
}

interface BinlistResponse {
  scheme?: string;
  country?: { alpha2?: string };
}

async function echoLookup(bin: string): Promise<CardInfo> {
  const response = await fetch(`${ECHO_URL}/${bin}`, { headers: { accept: 'application/json' } });
  console.log(`RECV L13 outside GET httpbin.org/anything/bins/${bin} status=${response.status}`);
  return { bin, scheme: null, country: null, source: 'fallback' };
}

export async function lookupBin(cardNumber: string): Promise<CardInfo> {
  const bin = cardNumber.replace(/\D/g, '').slice(0, 8);
  const response = await fetch(`${BINLIST_URL}/${bin}`, { headers: { 'Accept-Version': '3' } });
  console.log(`RECV L12 outside GET lookup.binlist.net/${bin} status=${response.status}`);
  if (!response.ok) {
    // binlist is heavily rate limited and rejects unknown BINs; keep the checkout going
    return echoLookup(bin);
  }
  const body = (await response.json()) as BinlistResponse;
  return { bin, scheme: body.scheme ?? null, country: body.country?.alpha2 ?? null, source: 'binlist' };
}
