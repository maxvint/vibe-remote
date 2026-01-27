import Redis from 'ioredis';
import { config } from './config.js';

let redis: Redis | null = null;

export function getRedis(): Redis {
  if (!redis) {
    redis = new Redis(config.redisUrl, {
      maxRetriesPerRequest: 3,
    });

    redis.on('error', (err) => {
      console.error('Redis error:', err);
    });

    redis.on('connect', () => {
      console.log('Connected to Redis');
    });
  }
  return redis;
}

export interface GitHubEvent {
  id: string;
  type: 'issue_comment' | 'issue';
  repo: string;
  issue_number: number;
  issue_title: string;
  issue_body: string;
  comment_id?: number;
  comment_url?: string;
  user: string;
  body: string;
  created_at: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  installation_id: string;
}

/**
 * Store event in Redis
 */
export async function storeEvent(event: GitHubEvent): Promise<void> {
  const redis = getRedis();
  const key = `${config.redisPrefix}event:${event.id}`;
  await redis.setex(key, config.eventTtl, JSON.stringify(event));
}

/**
 * Check if event is duplicate (by comment_id)
 */
export async function isDuplicate(commentId: number): Promise<boolean> {
  const redis = getRedis();
  const key = `${config.redisPrefix}processed:${commentId}`;
  const exists = await redis.exists(key);
  return exists === 1;
}

/**
 * Mark comment as processed
 */
export async function markProcessed(commentId: number): Promise<void> {
  const redis = getRedis();
  const key = `${config.redisPrefix}processed:${commentId}`;
  // Keep for 7 days to prevent duplicate processing
  await redis.setex(key, 7 * 24 * 60 * 60, '1');
}

/**
 * Get pending events (for fallback polling)
 */
export async function getPendingEvents(): Promise<GitHubEvent[]> {
  const redis = getRedis();
  const keys = await redis.keys(`${config.redisPrefix}event:*`);
  if (keys.length === 0) return [];

  const events: GitHubEvent[] = [];
  for (const key of keys) {
    const data = await redis.get(key);
    if (data) {
      try {
        const event = JSON.parse(data) as GitHubEvent;
        if (event.status === 'pending') {
          events.push(event);
        }
      } catch (e) {
        console.error(`Failed to parse event ${key}:`, e);
      }
    }
  }

  return events.sort((a, b) =>
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
}

/**
 * Delete event
 */
export async function deleteEvent(eventId: string): Promise<boolean> {
  const redis = getRedis();
  const key = `${config.redisPrefix}event:${eventId}`;
  const result = await redis.del(key);
  return result === 1;
}

export async function closeRedis(): Promise<void> {
  if (redis) {
    await redis.quit();
    redis = null;
  }
}
