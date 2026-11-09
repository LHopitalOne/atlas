import { SWRConfig } from 'swr';
import { fetcher } from '../lib/api';

export default function App({ Component, pageProps }) {
  return (
    <SWRConfig value={{ fetcher }}>
      <Component {...pageProps} />
    </SWRConfig>
  );
}
