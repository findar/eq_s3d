#!/usr/bin/env node
/**
 * dev.mjs — single-command dev launcher.
 *
 * Spawns the Python FastAPI backend (uvicorn) and the Vite dev server together,
 * waits for the backend to be healthy, and shuts both down cleanly on exit.
 *
 * Usage:  npm run dev          (from the web/ directory)
 *
 * No extra npm dependencies — uses only Node built-ins.
 */

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import process from "node:process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, "..");

const BACKEND_PORT = 8000;
// Use 127.0.0.1 (not localhost) — on Windows localhost may resolve to IPv6 ::1
// first, which uvicorn bound to 127.0.0.1 won't answer.
const HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/api/health`;

// ---------------------------------------------------------------------------
// Pick a Python command. Prefer a project venv, then fall back to PATH.
// ---------------------------------------------------------------------------
function pythonCommand() {
  const isWin = process.platform === "win32";
  const venvPython = isWin
    ? resolve(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
    : resolve(PROJECT_ROOT, ".venv", "bin", "python");

  // We can't easily stat here without fs; just try venv first via a flag.
  // Use fs to check existence.
  return { isWin, venvPython };
}

import { existsSync } from "node:fs";

function resolvePython() {
  const { isWin, venvPython } = pythonCommand();
  if (existsSync(venvPython)) return venvPython;
  // Fall back to python / python3 on PATH
  return isWin ? "python" : "python3";
}

// ---------------------------------------------------------------------------
// Child process management
// ---------------------------------------------------------------------------
const children = [];
let shuttingDown = false;

function prefixStream(stream, prefix, color) {
  let buffer = "";
  stream.on("data", (chunk) => {
    buffer += chunk.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim()) process.stdout.write(`${color}[${prefix}]\x1b[0m ${line}\n`);
    }
  });
}

function startBackend() {
  const python = resolvePython();
  console.log(`\x1b[36m[launcher]\x1b[0m starting backend: ${python} -m uvicorn server.app:app --host 127.0.0.1 --port ${BACKEND_PORT}`);

  const proc = spawn(
    python,
    ["-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    { cwd: PROJECT_ROOT, env: process.env }
  );

  prefixStream(proc.stdout, "api", "\x1b[32m");
  prefixStream(proc.stderr, "api", "\x1b[32m");

  proc.on("exit", (code) => {
    if (!shuttingDown) {
      console.error(`\x1b[31m[launcher]\x1b[0m backend exited (code ${code}). Shutting down.`);
      shutdown(1);
    }
  });

  children.push(proc);
  return proc;
}

function startFrontend() {
  console.log(`\x1b[36m[launcher]\x1b[0m starting Vite dev server`);
  // Invoke Vite's JS entry point directly with the current Node binary.
  // This avoids the .cmd shim + shell quoting problems when the project path
  // contains spaces (e.g. "F:\Dev Projects\...").
  const viteEntry = resolve(__dirname, "node_modules", "vite", "bin", "vite.js");

  const proc = spawn(process.execPath, [viteEntry], {
    cwd: __dirname,
    env: process.env,
  });

  prefixStream(proc.stdout, "web", "\x1b[35m");
  prefixStream(proc.stderr, "web", "\x1b[35m");

  proc.on("exit", (code) => {
    if (!shuttingDown) {
      console.error(`\x1b[31m[launcher]\x1b[0m frontend exited (code ${code}). Shutting down.`);
      shutdown(1);
    }
  });

  children.push(proc);
  return proc;
}

// ---------------------------------------------------------------------------
// Wait for backend health
// ---------------------------------------------------------------------------
async function waitForBackend(timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(HEALTH_URL);
      if (res.ok) return true;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

// ---------------------------------------------------------------------------
// Shutdown
// ---------------------------------------------------------------------------
function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`\n\x1b[36m[launcher]\x1b[0m shutting down…`);
  for (const child of children) {
    try {
      if (process.platform === "win32") {
        // Ensure the whole process tree dies (uvicorn + reloader)
        spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"]);
      } else {
        child.kill("SIGTERM");
      }
    } catch {
      // ignore
    }
  }
  setTimeout(() => process.exit(code), 500);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
(async () => {
  startBackend();

  console.log(`\x1b[36m[launcher]\x1b[0m waiting for backend to become healthy…`);
  const healthy = await waitForBackend();
  if (!healthy) {
    console.error(`\x1b[31m[launcher]\x1b[0m backend did not become healthy in time.`);
    shutdown(1);
    return;
  }
  console.log(`\x1b[36m[launcher]\x1b[0m backend ready → http://localhost:${BACKEND_PORT}`);

  startFrontend();
  console.log(`\x1b[36m[launcher]\x1b[0m open \x1b[1mhttp://localhost:5173\x1b[0m  (Ctrl+C to stop both)`);
})();
