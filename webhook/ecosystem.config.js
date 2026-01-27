module.exports = {
  apps: [{
    name: 'vibe-webhook',
    script: 'dist/index.js',
    cwd: __dirname,
    instances: 1,
    autorestart: true,
    port: 9123,
    watch: false,
    max_memory_restart: '256M',
    env_file: '.env',
    error_file: 'logs/error.log',
    out_file: 'logs/out.log',
    merge_logs: true,
    time: true
  }]
}
