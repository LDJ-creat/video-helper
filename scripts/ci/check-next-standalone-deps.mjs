import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

function exists(p) {
  try {
    fs.accessSync(p);
    return true;
  } catch {
    return false;
  }
}

function listDirs(p, limit = 60) {
  try {
    return fs
      .readdirSync(p, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => e.name)
      .slice(0, limit);
  } catch {
    return [];
  }
}

const targetDir = process.argv[2] ? path.resolve(process.argv[2]) : '';

if (!targetDir) {
  console.error('Usage: node scripts/ci/check-next-standalone-deps.mjs <standalone-app-dir>');
  process.exit(2);
}

if (!exists(targetDir) || !fs.statSync(targetDir).isDirectory()) {
  console.error(`Target directory not found or not a directory: ${targetDir}`);
  process.exit(2);
}

// Next standalone app dir should contain server.js. Use it as the resolution base.
const serverJs = path.join(targetDir, 'server.js');
const base = exists(serverJs) ? serverJs : path.join(targetDir, 'package.json');

if (!exists(base)) {
  console.error(`Neither server.js nor package.json exists in: ${targetDir}`);
  process.exit(2);
}

const requireFromStandalone = createRequire(pathToFileURL(base));

function isInside(child, parent) {
  const rel = path.relative(parent, child);
  return rel && !rel.startsWith('..') && !path.isAbsolute(rel);
}

try {
  const nextPkg = requireFromStandalone.resolve('next/package.json');
  const absNextPkg = path.resolve(nextPkg);
  const absTarget = path.resolve(targetDir);
  if (!isInside(absNextPkg, absTarget)) {
    throw new Error(
      `Resolved next/package.json outside targetDir (leaked to parent node_modules): ${absNextPkg}`
    );
  }
  const nextDir = path.dirname(nextPkg);
  const styledJsxPkg = requireFromStandalone.resolve('styled-jsx/package.json', {
    paths: [nextDir],
  });

  const absStyled = path.resolve(styledJsxPkg);
  if (!isInside(absStyled, absTarget)) {
    throw new Error(
      `Resolved styled-jsx/package.json outside targetDir (leaked to parent node_modules): ${absStyled}`
    );
  }

  if (!exists(styledJsxPkg)) {
    throw new Error(`Resolved styled-jsx package.json but file is missing: ${styledJsxPkg}`);
  }

  console.log('OK: styled-jsx is resolvable for Next runtime.');
  console.log(`next: ${nextPkg}`);
  console.log(`styled-jsx: ${styledJsxPkg}`);
  process.exit(0);
} catch (err) {
  const nm = path.join(targetDir, 'node_modules');
  const preview = listDirs(nm).join(', ');
  console.error('ERROR: styled-jsx is NOT resolvable for Next runtime.');
  console.error(`targetDir: ${targetDir}`);
  console.error(`node_modules exists: ${exists(nm)}`);
  if (preview) {
    console.error(`node_modules preview: [${preview}]`);
  }
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
}
