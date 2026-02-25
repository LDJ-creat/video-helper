const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function exists(p) {
  try {
    fs.accessSync(p);
    return true;
  } catch {
    return false;
  }
}

function rmrf(p) {
  try {
    fs.rmSync(p, { recursive: true, force: true });
  } catch {
    // ignore
  }
}

module.exports = async function beforePack(context) {
  // electron-builder hook context may differ across versions/platforms.
  // Derive paths from this script location for stability.
  const desktopDir = (context && context.appDir) ? context.appDir : path.resolve(__dirname, '..');
  const repoRoot = path.resolve(desktopDir, '..', '..');

  const standaloneWebDir = path.join(
    repoRoot,
    'apps',
    'web',
    '.next',
    'standalone',
    'apps',
    'web'
  );

  if (!exists(standaloneWebDir)) {
    throw new Error(
      `Next standalone output not found at: ${standaloneWebDir}. ` +
        `Run the web build first (BUILD_STANDALONE=1 pnpm -C apps/web build).`
    );
  }

  const checkScript = path.join(repoRoot, 'scripts', 'ci', 'check-next-standalone-deps.mjs');
  const nodeCmd = process.platform === 'win32' ? 'node.exe' : 'node';
  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const npmArgs = ['install', '--omit=dev', '--no-package-lock', '--loglevel=error'];

  function runCheck() {
    return spawnSync(nodeCmd, [checkScript, standaloneWebDir], {
      encoding: 'utf8',
      env: { ...process.env },
      shell: false,
    });
  }

  let checkRes = runCheck();
  if (checkRes.status !== 0) {
    // Ensure we don't keep a pnpm-style/symlinked node_modules from the standalone output.
    rmrf(path.join(standaloneWebDir, 'node_modules'));

    const res = spawnSync(npmCmd, npmArgs, {
      cwd: standaloneWebDir,
      stdio: 'inherit',
      env: {
        ...process.env,
        npm_config_progress: 'false',
      },
      shell: false,
    });

    if (res.status !== 0) {
      throw new Error(`Failed to hydrate standalone node_modules via npm (exit=${res.status}).`);
    }

    checkRes = runCheck();
  }

  if (checkRes.status !== 0) {
    const out = `${checkRes.stdout ?? ''}${checkRes.stderr ?? ''}`.trim();
    throw new Error(
      `Sanity check failed: standalone Next runtime deps are not resolvable after hydration.\n` +
        `standaloneWebDir: ${standaloneWebDir}\n` +
        (out ? `check output:\n${out}\n` : '')
    );
  }

  // Remove root standalone node_modules (pnpm virtual store) so it won't be
  // shipped as a large, non-resolvable tree.
  rmrf(path.join(repoRoot, 'apps', 'web', '.next', 'standalone', 'node_modules'));
};
