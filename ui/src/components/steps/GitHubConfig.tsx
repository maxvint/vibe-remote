import React, { useEffect, useState } from 'react';
import {
  Github,
  Key,
  Server,
  Settings,
  Check,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  RefreshCw,
  Shield,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import clsx from 'clsx';
import { useApi } from '../../context/ApiContext';
import type { GitHubInstallation, GitHubRepo } from '../../context/ApiContext';

interface GitHubConfigProps {
  data: any;
  onNext: (data: any) => void;
  onBack: () => void;
}

export const GitHubConfig: React.FC<GitHubConfigProps> = ({ data, onNext, onBack }) => {
  const { t } = useTranslation();
  const api = useApi();

  // GitHub App credentials
  const [appId, setAppId] = useState(data.github?.app_id || '');
  const [privateKey, setPrivateKey] = useState(data.github?.private_key || '');
  const [webhookSecret, setWebhookSecret] = useState(data.github?.webhook_secret || '');

  // Cloudflare Worker
  const [workerUrl, setWorkerUrl] = useState(data.github?.worker_url || '');
  const [workerToken, setWorkerToken] = useState(data.github?.worker_token || '');

  // Trigger settings
  const [triggerKeyword, setTriggerKeyword] = useState(data.github?.trigger_keyword || '@Codeholic');
  const [defaultAgent, setDefaultAgent] = useState(data.github?.default_agent || 'claude');

  // UI state
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({ 1: true });
  const [installations, setInstallations] = useState<GitHubInstallation[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [skipGitHub, setSkipGitHub] = useState(!data.github?.app_id);

  // Check if basic config is valid
  const isBasicConfigValid = appId && privateKey && workerUrl && workerToken;

  useEffect(() => {
    // Load existing repos if configured
    if (isBasicConfigValid && !skipGitHub) {
      loadRepos();
    }
  }, []);

  const loadRepos = async () => {
    setLoadingRepos(true);
    try {
      const result = await api.githubGetRepos();
      if (result.ok && result.installations) {
        setInstallations(result.installations);
      }
    } catch (err) {
      console.error('Failed to load GitHub repos:', err);
    } finally {
      setLoadingRepos(false);
    }
  };

  const toggleStep = (step: number) => {
    setExpandedSteps(prev => ({ ...prev, [step]: !prev[step] }));
  };

  const toggleRepoEnabled = async (installationId: string, repo: GitHubRepo) => {
    const newEnabled = !repo.enabled;
    try {
      await api.githubUpdateRepo(installationId, repo.full_name, { enabled: newEnabled });
      // Update local state
      setInstallations(prev => prev.map(inst => {
        if (inst.id === installationId) {
          return {
            ...inst,
            repos: inst.repos.map(r =>
              r.full_name === repo.full_name ? { ...r, enabled: newEnabled } : r
            )
          };
        }
        return inst;
      }));
    } catch (err) {
      console.error('Failed to update repo:', err);
    }
  };

  const openGitHubAppCreate = () => {
    window.open('https://github.com/settings/apps/new', '_blank');
  };

  const handleNext = () => {
    if (skipGitHub) {
      onNext({ github: null });
    } else {
      onNext({
        github: {
          app_id: appId,
          private_key: privateKey,
          webhook_secret: webhookSecret,
          worker_url: workerUrl,
          worker_token: workerToken,
          trigger_keyword: triggerKeyword,
          default_agent: defaultAgent,
        }
      });
    }
  };

  const StepHeader: React.FC<{ step: number; title: string; icon: React.ReactNode; completed?: boolean }> = ({ step, title, icon, completed }) => (
    <button
      onClick={() => toggleStep(step)}
      className="w-full px-4 py-3 flex items-center justify-between bg-neutral-50 hover:bg-neutral-100 transition-colors"
    >
      <div className="flex items-center gap-3">
        <span className={clsx(
          'w-7 h-7 rounded-full text-sm font-bold flex items-center justify-center transition-colors',
          completed ? 'bg-success text-white' : 'bg-accent text-white'
        )}>
          {completed ? <Check size={14} /> : step}
        </span>
        <span className="flex items-center gap-2 font-semibold text-text">
          {icon}
          {title}
        </span>
      </div>
      {expandedSteps[step] ? <ChevronUp size={18} className="text-muted" /> : <ChevronDown size={18} className="text-muted" />}
    </button>
  );

  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto">
      <div className="mb-4">
        <h2 className="text-3xl font-display font-bold text-text flex items-center gap-3">
          <Github size={32} />
          {t('githubConfig.title')}
        </h2>
        <p className="text-muted mt-1">{t('githubConfig.description')}</p>
      </div>

      {/* Skip GitHub toggle */}
      <div className="mb-4 p-4 bg-panel border border-border rounded-xl">
        <label className="flex items-center justify-between cursor-pointer">
          <div>
            <span className="font-medium text-text">{t('githubConfig.skipGitHub')}</span>
            <p className="text-sm text-muted">{t('githubConfig.skipGitHubHint')}</p>
          </div>
          <button
            onClick={() => setSkipGitHub(!skipGitHub)}
            className="text-accent"
          >
            {skipGitHub ? <ToggleLeft size={32} /> : <ToggleRight size={32} />}
          </button>
        </label>
      </div>

      {!skipGitHub && (
        <div className="space-y-3 overflow-y-auto flex-1 pr-1">
          {/* Step 1: Create GitHub App */}
          <div className="bg-panel border border-border rounded-xl overflow-hidden">
            <StepHeader
              step={1}
              title={t('githubConfig.step1Title')}
              icon={<Github size={16} className="text-accent" />}
              completed={!!appId && !!privateKey}
            />
            {expandedSteps[1] && (
              <div className="p-4 space-y-4 border-t border-border">
                <p className="text-sm text-muted">{t('githubConfig.step1Description')}</p>

                <button
                  onClick={openGitHubAppCreate}
                  className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors font-medium shadow-sm"
                >
                  <ExternalLink size={16} />
                  {t('githubConfig.createGitHubApp')}
                </button>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
                  <strong>{t('githubConfig.requiredPermissions')}:</strong>
                  <ul className="list-disc list-inside mt-1 space-y-0.5">
                    <li>Issues: Read & Write</li>
                    <li>Contents: Read-only</li>
                    <li>Metadata: Read-only</li>
                  </ul>
                </div>

                <div className="space-y-3 pt-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-text flex items-center gap-2">
                      <Key size={16} className="text-accent" /> {t('githubConfig.appId')}
                    </label>
                    <input
                      type="text"
                      value={appId}
                      onChange={(e) => setAppId(e.target.value)}
                      placeholder="123456"
                      className="w-full bg-bg border border-border rounded-lg p-3 text-text focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent font-mono transition-colors"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-text flex items-center gap-2">
                      <Shield size={16} className="text-accent" /> {t('githubConfig.privateKey')}
                    </label>
                    <textarea
                      value={privateKey}
                      onChange={(e) => setPrivateKey(e.target.value)}
                      placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
                      rows={4}
                      className="w-full bg-bg border border-border rounded-lg p-3 text-text focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent font-mono text-xs transition-colors"
                    />
                    <p className="text-xs text-muted">{t('githubConfig.privateKeyHint')}</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-text flex items-center gap-2">
                      <Key size={16} className="text-accent" /> {t('githubConfig.webhookSecret')}
                    </label>
                    <input
                      type="password"
                      value={webhookSecret}
                      onChange={(e) => setWebhookSecret(e.target.value)}
                      placeholder="your-webhook-secret"
                      className="w-full bg-bg border border-border rounded-lg p-3 text-text focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent font-mono transition-colors"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Step 2: Cloudflare Worker */}
          <div className="bg-panel border border-border rounded-xl overflow-hidden">
            <StepHeader
              step={2}
              title={t('githubConfig.step2Title')}
              icon={<Server size={16} className="text-accent" />}
              completed={!!workerUrl && !!workerToken}
            />
            {expandedSteps[2] && (
              <div className="p-4 space-y-4 border-t border-border">
                <p className="text-sm text-muted">{t('githubConfig.step2Description')}</p>

                <div className="space-y-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-text">{t('githubConfig.workerUrl')}</label>
                    <input
                      type="url"
                      value={workerUrl}
                      onChange={(e) => setWorkerUrl(e.target.value)}
                      placeholder="https://vibe-github-webhook.xxx.workers.dev"
                      className="w-full bg-bg border border-border rounded-lg p-3 text-text focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent font-mono transition-colors"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-text">{t('githubConfig.workerToken')}</label>
                    <input
                      type="password"
                      value={workerToken}
                      onChange={(e) => setWorkerToken(e.target.value)}
                      placeholder="sk-xxxxxxxxxxxxxxxx"
                      className="w-full bg-bg border border-border rounded-lg p-3 text-text focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent font-mono transition-colors"
                    />
                    <p className="text-xs text-muted">{t('githubConfig.workerTokenHint')}</p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Step 3: Trigger Settings */}
          <div className="bg-panel border border-border rounded-xl overflow-hidden">
            <StepHeader
              step={3}
              title={t('githubConfig.step3Title')}
              icon={<Settings size={16} className="text-accent" />}
              completed={!!triggerKeyword}
            />
            {expandedSteps[3] && (
              <div className="p-4 space-y-4 border-t border-border">
                <div className="space-y-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-text">{t('githubConfig.triggerKeyword')}</label>
                    <input
                      type="text"
                      value={triggerKeyword}
                      onChange={(e) => setTriggerKeyword(e.target.value)}
                      placeholder="@Codeholic"
                      className="w-full bg-bg border border-border rounded-lg p-3 text-text focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors"
                    />
                    <p className="text-xs text-muted">{t('githubConfig.triggerKeywordHint')}</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-text">{t('githubConfig.defaultAgent')}</label>
                    <select
                      value={defaultAgent}
                      onChange={(e) => setDefaultAgent(e.target.value)}
                      className="w-full bg-bg border border-border rounded-lg p-3 text-text focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors"
                    >
                      <option value="claude">Claude Code</option>
                      <option value="opencode">OpenCode</option>
                      <option value="codex">Codex</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Step 4: Repositories */}
          <div className="bg-panel border border-border rounded-xl overflow-hidden">
            <StepHeader
              step={4}
              title={t('githubConfig.step4Title')}
              icon={<Github size={16} className="text-accent" />}
            />
            {expandedSteps[4] && (
              <div className="p-4 space-y-4 border-t border-border">
                <p className="text-sm text-muted">{t('githubConfig.step4Description')}</p>

                <div className="flex items-center gap-3">
                  <button
                    onClick={loadRepos}
                    disabled={!isBasicConfigValid || loadingRepos}
                    className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium shadow-sm"
                  >
                    {loadingRepos ? <RefreshCw size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                    {t('githubConfig.refreshRepos')}
                  </button>
                </div>

                {installations.length > 0 ? (
                  <div className="space-y-3">
                    {installations.map(inst => (
                      <div key={inst.id} className="border border-border rounded-lg overflow-hidden">
                        <div className="px-3 py-2 bg-neutral-50 font-medium text-sm">
                          {inst.account} ({inst.account_type})
                        </div>
                        <div className="divide-y divide-border">
                          {inst.repos.map(repo => (
                            <div key={repo.full_name} className="px-3 py-2 flex items-center justify-between">
                              <span className="text-sm font-mono">{repo.full_name}</span>
                              <button
                                onClick={() => toggleRepoEnabled(inst.id, repo)}
                                className={clsx(
                                  'px-3 py-1 rounded-full text-xs font-medium transition-colors',
                                  repo.enabled
                                    ? 'bg-success/10 text-success border border-success/20'
                                    : 'bg-neutral-100 text-muted border border-border'
                                )}
                              >
                                {repo.enabled ? t('githubConfig.enabled') : t('githubConfig.disabled')}
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6 text-muted">
                    {loadingRepos ? t('common.loading') : t('githubConfig.noRepos')}
                  </div>
                )}

                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800">
                  <strong>{t('githubConfig.note')}:</strong> {t('githubConfig.step4Note')}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mt-auto flex justify-between pt-6 border-t border-border">
        <button
          onClick={onBack}
          className="px-6 py-2 text-muted hover:text-text font-medium transition-colors"
        >
          {t('common.back')}
        </button>
        <button
          onClick={handleNext}
          disabled={!skipGitHub && !isBasicConfigValid}
          className={clsx(
            'px-8 py-3 rounded-lg font-medium transition-colors shadow-sm',
            (skipGitHub || isBasicConfigValid)
              ? 'bg-accent hover:bg-accent/90 text-white'
              : 'bg-neutral-200 text-muted cursor-not-allowed'
          )}
        >
          {t('common.continue')}
        </button>
      </div>
    </div>
  );
};
