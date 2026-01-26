import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { LayoutDashboard, MessageSquare, Activity, Github, ChevronDown, ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useStatus } from '../context/StatusContext';
import { useApi } from '../context/ApiContext';
import { LanguageSwitcher } from './LanguageSwitcher';
import { VersionBadge } from './VersionBadge';
import clsx from 'clsx';
import logoImg from '../assets/logo.png';

const NavItem = ({ to, icon: Icon, children }: { to: string; icon: any; children: React.ReactNode }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      clsx(
        'flex items-center gap-3 px-3 py-2 rounded-md transition-colors',
        isActive ? 'bg-accent/10 text-accent font-medium' : 'text-muted hover:bg-neutral-100 hover:text-text'
      )
    }
  >
    <Icon className="w-5 h-5" />
    <span>{children}</span>
  </NavLink>
);

export const AppShell: React.FC = () => {
  const { t } = useTranslation();
  const { status } = useStatus();
  const { githubInstallations, loadGithubInstallations } = useApi();
  const location = useLocation();
  const [githubExpanded, setGithubExpanded] = React.useState(true);
  const [config, setConfig] = React.useState<any>({});

  const isRunning = status.state === 'running';

  // Load config and GitHub repos
  React.useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch('/config');
        if (res.ok) {
          const cfg = await res.json();
          setConfig(cfg);
          if (cfg.github?.app_id && cfg.github?.worker_url) {
            loadGithubInstallations();
          }
        }
      } catch {
        // ignore
      }
    };
    load();
  }, [loadGithubInstallations]);

  // Get enabled repos
  const enabledRepos = React.useMemo(() => {
    console.log('[AppShell] computing enabledRepos, githubInstallations:', githubInstallations);
    const repos: { installationId: string; fullName: string; name: string }[] = [];
    for (const inst of githubInstallations) {
      console.log('[AppShell] inst:', inst.id, 'repos:', inst.repos.map(r => ({ name: r.full_name, enabled: r.enabled })));
      for (const repo of inst.repos) {
        if (repo.enabled) {
          repos.push({
            installationId: inst.id,
            fullName: repo.full_name,
            name: repo.full_name.split('/')[1] || repo.full_name,
          });
        }
      }
    }
    console.log('[AppShell] enabledRepos:', repos);
    return repos;
  }, [githubInstallations]);

  const hasGitHubConfig = config.github?.app_id && config.github?.worker_url;

  if (location.pathname === '/setup') {
    return <Outlet />;
  }

  return (
    <div className="min-h-screen flex bg-bg text-text font-sans">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-panel hidden md:flex flex-col">
        <div className="p-6 border-b border-border">
            <div className="flex items-center gap-3">
                <img src={logoImg} alt="Vibe Remote Logo" className="w-10 h-10 rounded-lg" />
                <div className="flex flex-col">
                    <h1 className="text-xl font-bold font-display tracking-tight leading-tight">
                        {t('appShell.title')}
                    </h1>
                    <VersionBadge />
                </div>
            </div>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          <NavItem to="/dashboard" icon={LayoutDashboard}>{t('nav.dashboard')}</NavItem>
          <NavItem to="/channels" icon={MessageSquare}>{t('nav.channels')}</NavItem>
          <NavItem to="/doctor" icon={Activity}>{t('nav.doctor')}</NavItem>

          {/* GitHub Repos Section */}
          <div className="pt-4 mt-4 border-t border-border">
            <button
              onClick={() => setGithubExpanded(!githubExpanded)}
              className="flex items-center justify-between w-full px-3 py-2 text-sm font-medium text-muted hover:text-text transition-colors"
            >
              <span className="flex items-center gap-2">
                <Github className="w-4 h-4" />
                {t('nav.githubRepos')}
              </span>
              {githubExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
            {githubExpanded && (
              <div className="mt-1 space-y-0.5">
                {!hasGitHubConfig ? (
                  <NavLink
                    to="/setup"
                    className="flex items-center gap-2 px-3 py-1.5 pl-8 text-sm text-accent hover:bg-neutral-100 rounded-md transition-colors"
                  >
                    {t('nav.configureGitHub')}
                  </NavLink>
                ) : enabledRepos.length > 0 ? (
                  enabledRepos.map((repo) => (
                    <a
                      key={repo.fullName}
                      href={`https://github.com/${repo.fullName}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-3 py-1.5 pl-8 text-sm text-muted hover:text-text hover:bg-neutral-100 rounded-md transition-colors"
                      title={repo.fullName}
                    >
                      <span className="truncate">{repo.name}</span>
                    </a>
                  ))
                ) : (
                  <div className="px-3 py-2 pl-8 text-xs text-muted">
                    {t('nav.noEnabledRepos')}
                  </div>
                )}
              </div>
            )}
          </div>
        </nav>

        <div className="p-4 border-t border-border space-y-3">
             <LanguageSwitcher />
             <div className="flex items-center justify-between bg-neutral-50 p-3 rounded-lg border border-border">
                <div className="flex items-center gap-2">
                    <div className={clsx("w-2.5 h-2.5 rounded-full", isRunning ? "bg-success" : "bg-muted")}></div>
                    <span className="text-sm font-medium">{isRunning ? t('common.running') : t('common.stopped')}</span>
                </div>
             </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto p-4 md:p-8">
        <Outlet />
      </main>

       {/* Mobile Nav */}
       <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-panel border-t border-border flex justify-around p-3 z-50 pb-safe">
          <NavLink to="/dashboard" className={({isActive}) => clsx("p-2 rounded-lg", isActive ? "text-accent" : "text-muted")}><LayoutDashboard /></NavLink>
          <NavLink to="/channels" className={({isActive}) => clsx("p-2 rounded-lg", isActive ? "text-accent" : "text-muted")}><MessageSquare /></NavLink>
          <NavLink to="/doctor" className={({isActive}) => clsx("p-2 rounded-lg", isActive ? "text-accent" : "text-muted")}><Activity /></NavLink>
       </nav>
    </div>
  );
};
