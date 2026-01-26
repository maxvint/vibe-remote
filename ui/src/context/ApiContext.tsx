import React, { createContext, useContext, useState, useCallback } from 'react';
import { useToast } from './ToastContext';

export type GitHubInstallation = {
  id: string;
  account: string;
  account_type: string;
  repos: GitHubRepo[];
};

export type GitHubRepo = {
  full_name: string;
  name?: string;
  private?: boolean;
  enabled: boolean;
  agent: string;
  cwd: string | null;
  allowed_users: string[];
};

export type ApiContextType = {
  getConfig: () => Promise<any>;
  saveConfig: (payload: any) => Promise<any>;
  getSettings: () => Promise<any>;
  saveSettings: (payload: any) => Promise<any>;
  detectCli: (binary: string) => Promise<any>;
  slackAuthTest: (botToken: string) => Promise<any>;
  slackChannels: (botToken: string) => Promise<any>;
  slackManifest: () => Promise<{ ok: boolean; manifest?: string; manifest_compact?: string; error?: string }>;
  doctor: () => Promise<any>;
  opencodeOptions: (cwd: string) => Promise<any>;
  getLogs: (lines?: number) => Promise<{ logs: LogEntry[]; total: number }>;
  getVersion: () => Promise<VersionInfo>;
  doUpgrade: () => Promise<UpgradeResult>;
  // GitHub Integration
  githubGetInstallUrl: () => Promise<{ ok: boolean; app_id?: string; message?: string; error?: string }>;
  githubGetRepos: () => Promise<{ ok: boolean; installations?: GitHubInstallation[]; error?: string }>;
  githubUpdateRepo: (installationId: string, repo: string, settings: Partial<GitHubRepo>) => Promise<{ ok: boolean; error?: string }>;
  githubRefreshRepos: (installationId: string) => Promise<{ ok: boolean; repos?: any[]; error?: string }>;
  // Shared GitHub state
  githubInstallations: GitHubInstallation[];
  githubLoading: boolean;
  loadGithubInstallations: () => Promise<void>;
  updateLocalGithubRepo: (installationId: string, repoFullName: string, enabled: boolean) => void;
};

export type LogEntry = {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
};

export type VersionInfo = {
  current: string;
  latest: string | null;
  has_update: boolean;
  error: string | null;
};

export type UpgradeResult = {
  ok: boolean;
  message: string;
  output: string | null;
  restarting: boolean;
};

const ApiContext = createContext<ApiContextType | undefined>(undefined);

export const useApi = () => {
  const context = useContext(ApiContext);
  if (!context) {
    throw new Error('useApi must be used within ApiProvider');
  }
  return context;
};

export const ApiProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { showToast } = useToast();
  const [githubInstallations, setGithubInstallations] = useState<GitHubInstallation[]>([]);
  const [githubLoading, setGithubLoading] = useState(false);

  const handleApiError = async (res: Response, path: string) => {
    let errorMessage = `Request failed: ${path} (${res.status})`;
    
    try {
      const data = await res.json();
      if (data.error) {
        errorMessage = data.error;
      }
    } catch {
      // Response is not JSON, use status text
      errorMessage = `${path}: ${res.statusText || 'Unknown error'} (${res.status})`;
    }

    // Log error details to console
    console.error(`[API Error] ${path}`, {
      status: res.status,
      statusText: res.statusText,
      error: errorMessage,
    });

    // Show toast to user
    showToast(errorMessage, 'error');

    throw new Error(errorMessage);
  };

  const getJson = async (path: string) => {
    const res = await fetch(path);
    if (!res.ok) {
      await handleApiError(res, path);
    }
    return res.json();
  };

  const postJson = async (path: string, payload: any) => {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      await handleApiError(res, path);
    }
    return res.json();
  };

  const loadGithubInstallations = useCallback(async () => {
    setGithubLoading(true);
    try {
      const res = await fetch('/github/repos');
      if (!res.ok) {
        return;
      }
      const result = await res.json();
      console.log('[ApiContext] loadGithubInstallations result:', result);
      if (result.ok && result.installations) {
        for (const inst of result.installations) {
          console.log('[ApiContext] installation:', inst.id, 'repos:', inst.repos.map((r: GitHubRepo) => ({ name: r.full_name, enabled: r.enabled })));
        }
        setGithubInstallations(result.installations);
      }
    } catch (e) {
      console.error('[ApiContext] loadGithubInstallations error:', e);
    } finally {
      setGithubLoading(false);
    }
  }, []);

  const updateLocalGithubRepo = useCallback((installationId: string, repoFullName: string, enabled: boolean) => {
    console.log('[ApiContext] updateLocalGithubRepo:', { installationId, repoFullName, enabled });
    setGithubInstallations(prev => {
      const next = prev.map(inst => {
        if (inst.id === installationId) {
          return {
            ...inst,
            repos: inst.repos.map(r =>
              r.full_name === repoFullName ? { ...r, enabled } : r
            )
          };
        }
        return inst;
      });
      console.log('[ApiContext] githubInstallations updated:', next);
      return next;
    });
  }, []);

  const value: ApiContextType = {
    getConfig: () => getJson('/config'),
    saveConfig: (payload) => postJson('/config', payload),
    getSettings: () => getJson('/settings'),
    saveSettings: (payload) => postJson('/settings', payload),
    detectCli: (binary) => getJson(`/cli/detect?binary=${encodeURIComponent(binary)}`),
    slackAuthTest: (botToken) => postJson('/slack/auth_test', { bot_token: botToken }),
    slackChannels: (botToken) => postJson('/slack/channels', { bot_token: botToken }),
    slackManifest: () => getJson('/slack/manifest'),
    doctor: () => postJson('/doctor', {}),
    opencodeOptions: (cwd) => postJson('/opencode/options', { cwd }),
    getLogs: (lines = 500) => postJson('/logs', { lines }),
    getVersion: () => getJson('/version'),
    doUpgrade: () => postJson('/upgrade', {}),
    // GitHub Integration
    githubGetInstallUrl: () => getJson('/github/install'),
    githubGetRepos: () => getJson('/github/repos'),
    githubUpdateRepo: (installationId, repo, settings) =>
      postJson('/github/repos', { installation_id: installationId, repo, settings }),
    githubRefreshRepos: (installationId) =>
      postJson('/github/repos/refresh', { installation_id: installationId }),
    // Shared GitHub state
    githubInstallations,
    githubLoading,
    loadGithubInstallations,
    updateLocalGithubRepo,
  };

  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>;
};
