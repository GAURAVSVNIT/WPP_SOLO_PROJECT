// Set the NODE_OPTIONS environment variable
process.env.NODE_OPTIONS = '--openssl-legacy-provider';

// Spawn webpack process
const { spawnSync } = require('child_process');
const result = spawnSync('npx', ['webpack', '--mode', 'production'], {
  stdio: 'inherit',
  env: process.env
});

// Exit with the same code as webpack
process.exit(result.status);
