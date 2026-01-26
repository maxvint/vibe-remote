import crypto from 'crypto';
import { config } from './config.js';
import {
  storeEvent,
  isDuplicate,
  markProcessed,
  type GitHubEvent,
} from './redis.js';
import { pushToVibeRemote } from './push.js';

interface IssueCommentPayload {
  action: string;
  issue: {
    number: number;
    title: string;
    body: string | null;
    html_url: string;
  };
  comment: {
    id: number;
    body: string;
    html_url: string;
    user: {
      login: string;
    };
  };
  repository: {
    full_name: string;
  };
  installation?: {
    id: number;
  };
}

/**
 * Verify GitHub webhook signature
 */
export function verifySignature(
  payload: string,
  signature: string | undefined
): boolean {
  if (!config.webhookSecret) {
    console.warn('Webhook secret not configured, skipping verification');
    return true;
  }

  if (!signature) {
    return false;
  }

  const expected = `sha256=${crypto
    .createHmac('sha256', config.webhookSecret)
    .update(payload)
    .digest('hex')}`;

  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}

/**
 * Extract instruction from comment body (remove trigger keyword)
 */
function extractInstruction(body: string, keyword: string): string {
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`${escaped}(:\\w+)?\\s*`, 'g');
  return body.replace(pattern, '').trim();
}

/**
 * Handle GitHub webhook
 */
export async function handleWebhook(
  payload: IssueCommentPayload
): Promise<{ success: boolean; message: string; eventId?: string }> {
  // Only handle created comments
  if (payload.action !== 'created') {
    return { success: true, message: 'Skipped: not a created event' };
  }

  const commentBody = payload.comment?.body || '';
  const commentId = payload.comment?.id;

  // Check for trigger keyword
  const matchedKeyword = config.triggerKeywords.find((kw) =>
    commentBody.includes(kw)
  );

  if (!matchedKeyword) {
    return { success: true, message: 'Skipped: no trigger keyword' };
  }

  // Check for duplicate
  if (commentId && (await isDuplicate(commentId))) {
    return { success: true, message: 'Skipped: duplicate event' };
  }

  // Extract instruction
  const body = extractInstruction(commentBody, matchedKeyword);

  // Build event
  const event: GitHubEvent = {
    id: crypto.randomUUID(),
    type: 'issue_comment',
    repo: payload.repository.full_name,
    issue_number: payload.issue.number,
    issue_title: payload.issue.title,
    issue_body: payload.issue.body || '',
    comment_id: payload.comment.id,
    comment_url: payload.comment.html_url,
    user: payload.comment.user.login,
    body,
    created_at: new Date().toISOString(),
    status: 'pending',
    installation_id: String(payload.installation?.id || ''),
  };

  // Store in Redis (for backup/audit)
  await storeEvent(event);

  // Mark as processed to prevent duplicates
  if (commentId) {
    await markProcessed(commentId);
  }

  // Push to vibe-remote
  const pushed = await pushToVibeRemote(event);

  if (pushed) {
    return {
      success: true,
      message: 'Event pushed to vibe-remote',
      eventId: event.id,
    };
  } else {
    // Event is stored in Redis, can be polled later
    return {
      success: true,
      message: 'Event stored, push failed (will be polled)',
      eventId: event.id,
    };
  }
}
