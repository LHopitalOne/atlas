import Fastify from 'fastify';

import { registerWebhook } from './clients/provider.ts';
import { config } from './config.ts';
import { apiRoutes } from './routes/api.ts';
import { webhookRoutes } from './routes/webhooks.ts';
import { session } from './session.ts';

const app = Fastify({ logger: false });

app.addHook('onSend', async (_request, reply) => {
  reply.header('access-control-allow-origin', '*');
});

app.register(apiRoutes, { prefix: '/api' });
app.register(webhookRoutes, { prefix: '/webhooks' });
app.get('/healthz', async () => ({ ok: true, registered: Boolean(session.merchantId) }));

async function registerWithProvider(): Promise<void> {
  const webhookUrl = new URL('/webhooks/payhooks', config.publicUrl).toString();
  for (let attempt = 1; ; attempt += 1) {
    try {
      const registration = await registerWebhook(webhookUrl);
      session.merchantId = registration.id;
      session.signingSecret = registration.signing_secret;
      console.log(`merchant registered as ${registration.id} with webhook ${webhookUrl}`);
      return;
    } catch (err) {
      if (attempt >= 30) throw err;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
}

await app.listen({ port: config.port, host: '127.0.0.1' });
console.log(`merchant listening on ${config.port}`);
await registerWithProvider();
