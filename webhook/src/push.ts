import { config } from './config.js';
import type { GitHubEvent } from './redis.js';

/**
 * Push event directly to vibe-remote
 */
export async function pushToVibeRemote(event: GitHubEvent): Promise<boolean> {
  const url = `${config.vibeRemoteUrl}/github/webhook`;

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (config.pushToken) {
      headers['Authorization'] = `Bearer ${config.pushToken}`;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(event),
    });

    if (!response.ok) {
      const text = await response.text();
      console.error(`Push to vibe-remote failed: ${response.status} ${text}`);
      return false;
    }

    console.log(`Event ${event.id} pushed to vibe-remote successfully`);
    return true;
  } catch (error) {
    console.error(`Failed to push event ${event.id} to vibe-remote:`, error);
    return false;
  }
}
