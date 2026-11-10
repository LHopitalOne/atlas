import axios from 'axios';

// The SPA only ever talks to the edge gateway, which is served from the same origin.
export const http = axios.create({
  baseURL: '/api',
  timeout: 5000,
  headers: { Accept: 'application/json' },
});
