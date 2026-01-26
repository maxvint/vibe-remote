import Fastify from 'fastify';
import { config, validateConfig } from './config.js';
import { handleWebhook, verifySignature } from './webhook.js';
import {
  getPendingEvents,
  deleteEvent,
  closeRedis,
} from './redis.js';

const fastify = Fastify({
  logger: true,
});

// Health check
fastify.get('/health', async () => {
  return { status: 'ok', timestamp: new Date().toISOString() };
});

// GitHub Webhook endpoint
fastify.post('/webhook', async (request, reply) => {
  const signature = request.headers['x-hub-signature-256'] as string | undefined;
  const rawBody = JSON.stringify(request.body);

  // Verify signature
  if (!verifySignature(rawBody, signature)) {
    return reply.status(401).send({ error: 'Invalid signature' });
  }

  try {
    const result = await handleWebhook(request.body as any);
    return result;
  } catch (error) {
    fastify.log.error(error);
    return reply.status(500).send({ error: 'Internal server error' });
  }
});

// Get pending events (fallback for polling)
fastify.get('/events', async (request, reply) => {
  const authHeader = request.headers.authorization;
  if (config.pushToken && authHeader !== `Bearer ${config.pushToken}`) {
    return reply.status(401).send({ error: 'Unauthorized' });
  }

  try {
    const events = await getPendingEvents();
    return { events };
  } catch (error) {
    fastify.log.error(error);
    return reply.status(500).send({ error: 'Internal server error' });
  }
});

// Delete event (mark as processed)
fastify.delete('/events/:eventId', async (request, reply) => {
  const authHeader = request.headers.authorization;
  if (config.pushToken && authHeader !== `Bearer ${config.pushToken}`) {
    return reply.status(401).send({ error: 'Unauthorized' });
  }

  const { eventId } = request.params as { eventId: string };

  try {
    const deleted = await deleteEvent(eventId);
    return { success: deleted };
  } catch (error) {
    fastify.log.error(error);
    return reply.status(500).send({ error: 'Internal server error' });
  }
});

// Graceful shutdown
async function shutdown() {
  console.log('Shutting down...');
  await fastify.close();
  await closeRedis();
  process.exit(0);
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

// Start server
async function start() {
  try {
    validateConfig();
    await fastify.listen({ port: config.port, host: config.host });
    console.log(`Webhook server listening on ${config.host}:${config.port}`);
    console.log(`Trigger keywords: ${config.triggerKeywords.join(', ')}`);
    console.log(`Push target: ${config.vibeRemoteUrl}`);
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}

start();
