const fs = require('fs').promises;
const path = require('path');

async function getLatestRelease(repo, token) {
  const url = `https://api.github.com/repos/${repo}/releases/latest`;
  const headers = { 'User-Agent': 'version-checker' };
  if (token) headers['Authorization'] = `token ${token}`;
  const res = await fetch(url, { headers });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GitHub API error ${res.status}`);
  const data = await res.json();
  return data.tag_name || data.name || null;
}

function normalize(v) {
  if (!v) return null;
  return String(v).trim().replace(/^v/i, '');
}

function compareSemver(a, b) {
  // return -1 if a < b, 0 if equal, 1 if a > b
  const pa = (a || '').split('-')[0].split('.').map(n => parseInt(n || '0', 10));
  const pb = (b || '').split('-')[0].split('.').map(n => parseInt(n || '0', 10));
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] || 0;
    const nb = pb[i] || 0;
    if (na < nb) return -1;
    if (na > nb) return 1;
  }
  return 0;
}

async function findPackageJsons(dir) {
  const results = [];
  async function walk(current) {
    const names = await fs.readdir(current, { withFileTypes: true });
    for (const ent of names) {
      if (ent.name === 'node_modules' || ent.name === '.git' || ent.name === 'dist') continue;
      const full = path.join(current, ent.name);
      if (ent.isDirectory()) {
        await walk(full);
      } else if (ent.isFile() && ent.name === 'package.json') {
        results.push(full);
      }
    }
  }
  await walk(dir);
  return results;
}

async function main() {
  try {
    const repo = process.env.GITHUB_REPOSITORY;
    if (!repo) {
      console.log('GITHUB_REPOSITORY not set, skipping check.');
      return;
    }
    const token = process.env.GITHUB_TOKEN;
    const rawLatest = await getLatestRelease(repo, token).catch(e => {
      console.error('Failed to fetch latest release:', e.message);
      return null;
    });
    if (!rawLatest) {
      console.log('No releases found; skipping version comparison.');
      return;
    }
    const latest = normalize(rawLatest);
    if (!latest) {
      console.log('Latest release tag could not be parsed; skipping.');
      return;
    }

    const cwd = process.cwd();
    const pkgFiles = await findPackageJsons(cwd);
    if (!pkgFiles.length) {
      console.log('No package.json files found.');
      return;
    }

    let hadOutdated = false;
    for (const file of pkgFiles) {
      try {
        const content = await fs.readFile(file, 'utf8');
        const pkg = JSON.parse(content);
        const ver = normalize(pkg.version);
        if (!ver) continue;
        const cmp = compareSemver(ver, latest);
        if (cmp === -1) {
          hadOutdated = true;
          // GitHub Actions warning annotation
          console.log(`::warning file=${file},title=Outdated package version::${path.relative(cwd, file)} version ${ver} is older than latest release ${latest}`);
        }
      } catch (e) {
        console.log(`Skipping ${file}: ${e.message}`);
      }
    }

    if (hadOutdated) {
      if (String(process.env.FAIL_ON_OUTDATED).toLowerCase() === 'true') {
        console.error('One or more package.json files have versions older than latest release. Failing as requested.');
        process.exit(1);
      } else {
        console.log('Warning emitted for outdated package versions.');
      }
    } else {
      console.log('All package.json versions are >= latest release.');
    }
  } catch (e) {
    console.error('Unexpected error:', e.message);
    process.exit(2);
  }
}

main();
