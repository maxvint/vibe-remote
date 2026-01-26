/**
 * Configuration from environment variables
 */
export const config = {
  // Server
  port: parseInt(process.env.PORT || '3000', 10),
  host: process.env.HOST || '0.0.0.0',

  // GitHub
  webhookSecret: process.env.GITHUB_WEBHOOK_SECRET || '',
  triggerKeywords: (process.env.TRIGGER_KEYWORDS || '@Codeholic')
    .split(',')
    .map(k => k.trim())
    .filter(k => k.length > 0),

  // Redis
  redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',
  redisPrefix: process.env.REDIS_PREFIX || 'vibe:webhook:',
  eventTtl: parseInt(process.env.EVENT_TTL || '86400', 10), // 24 hours

  // Push to vibe-remote
  vibeRemoteUrl: process.env.VIBE_REMOTE_URL || 'http://localhost:5123',
  pushToken: process.env.PUSH_TOKEN || '', // Optional auth token
};

export function validateConfig(): void {
  if (!config.webhookSecret) {
    console.warn('Warning: GITHUB_WEBHOOK_SECRET not set, webhook signature verification disabled');
  }
  if (!config.vibeRemoteUrl) {
    throw new Error('VIBE_REMOTE_URL is required');
  }
}
