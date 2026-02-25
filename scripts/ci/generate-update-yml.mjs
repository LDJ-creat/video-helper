import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

function sha512Base64(filePath) {
  const buf = fs.readFileSync(filePath);
  return crypto.createHash('sha512').update(buf).digest('base64');
}

function fileSize(filePath) {
  return fs.statSync(filePath).size;
}

function findFirst(dir, predicate) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      const found = findFirst(full, predicate);
      if (found) return found;
    } else if (e.isFile()) {
      if (predicate(full)) return full;
    }
  }
  return null;
}

function toPosix(p) {
  return p.split(path.sep).join('/');
}

function writeLatestYaml({ outDir, filePath, ymlName, version }) {
  const fileName = path.basename(filePath);
  const sha512 = sha512Base64(filePath);
  const size = fileSize(filePath);
  const releaseDate = new Date().toISOString();

  const yml = [
    `version: ${version}`,
    `files:`,
    `  - url: ${fileName}`,
    `    sha512: ${sha512}`,
    `    size: ${size}`,
    `path: ${fileName}`,
    `sha512: ${sha512}`,
    `releaseDate: '${releaseDate}'`,
    '',
  ].join('\n');

  const outPath = path.join(outDir, ymlName);
  fs.writeFileSync(outPath, yml, 'utf8');
  process.stdout.write(`Generated ${toPosix(outPath)} -> ${fileName}\n`);
}

const outputDir = process.argv[2];
if (!outputDir) {
  console.error('Usage: node scripts/ci/generate-update-yml.mjs <apps/desktop/release>');
  process.exit(2);
}

const repoRoot = process.cwd();
const desktopPkgPath = path.join(repoRoot, 'apps', 'desktop', 'package.json');
const desktopPkg = JSON.parse(fs.readFileSync(desktopPkgPath, 'utf8'));
const version = desktopPkg.version;

const runnerOs = process.env.RUNNER_OS || '';

if (runnerOs === 'Windows') {
  const exe = findFirst(outputDir, (p) => /Video Helper Setup .*\.exe$/i.test(p) && !p.toLowerCase().endsWith('.exe.blockmap'));
  if (!exe) throw new Error(`Windows installer exe not found under ${outputDir}`);
  writeLatestYaml({ outDir: outputDir, filePath: exe, ymlName: 'latest.yml', version });
} else if (runnerOs === 'macOS') {
  const zip = findFirst(outputDir, (p) => p.toLowerCase().endsWith('.zip'));
  if (!zip) throw new Error(`macOS update zip not found under ${outputDir}`);
  writeLatestYaml({ outDir: outputDir, filePath: zip, ymlName: 'latest-mac.yml', version });
} else if (runnerOs === 'Linux') {
  const appImage = findFirst(outputDir, (p) => p.toLowerCase().endsWith('.appimage'));
  if (!appImage) throw new Error(`Linux AppImage not found under ${outputDir}`);
  writeLatestYaml({ outDir: outputDir, filePath: appImage, ymlName: 'latest-linux.yml', version });
} else {
  // Best-effort fallback: generate Windows-style metadata if an exe exists.
  const exe = findFirst(outputDir, (p) => p.toLowerCase().endsWith('.exe') && !p.toLowerCase().endsWith('.exe.blockmap'));
  if (exe) {
    writeLatestYaml({ outDir: outputDir, filePath: exe, ymlName: 'latest.yml', version });
  } else {
    process.stdout.write(`RUNNER_OS not set or unsupported (${runnerOs}); skipping update yml generation.\n`);
  }
}
