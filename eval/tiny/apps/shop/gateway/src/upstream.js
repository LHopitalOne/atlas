const axios = require('axios');
const config = require('./config');

const catalogApi = axios.create({
  baseURL: config.catalogUrl,
  timeout: config.upstreamTimeoutMs,
});

const ordersApi = axios.create({
  baseURL: config.ordersUrl,
  timeout: config.upstreamTimeoutMs,
});

async function listProducts(params = {}) {
  const res = await catalogApi.get('/products', { params });
  return res.data;
}

async function getProduct(id) {
  const res = await catalogApi.get(`/products/${encodeURIComponent(id)}`);
  return res.data;
}

async function createOrder(order) {
  const res = await ordersApi.post('/orders', order);
  return res.data;
}

async function getOrder(id) {
  const res = await ordersApi.get(`/orders/${encodeURIComponent(id)}`);
  return res.data;
}

module.exports = { listProducts, getProduct, createOrder, getOrder };
