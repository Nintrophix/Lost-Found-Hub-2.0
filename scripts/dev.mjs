// Development commands that work from the repository root on Windows, macOS and Linux.
// Usage: node scripts/dev.mjs <setup|backend|frontend|cli|test> [args...]
// (or the matching `npm run` scripts in the root package.json)
import { spawn, spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, watch } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const backend = join(root, 'backend');
const frontend = join(root, 'frontend');
const isWindows = process.platform === 'win32';
const venvPython = join(backend, '.venv', isWindows ? 'Scripts/python.exe' : 'bin/python');

function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', shell: isWindows && command === 'npm' });
  if (result.error) {
    console.error(`Could not run ${command}: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

/**
 * Run a long-lived server and exit with its exit code. SIGINT is ignored here because the server
 * receives the same Ctrl+C from the console: it stops itself, and then this script exits.
 */
function serve(command, args, cwd) {
  process.on('SIGINT', () => {});
  const child = spawn(command, args, { cwd, stdio: 'inherit', shell: isWindows && command === 'npm' });
  child.on('error', (error) => {
    console.error(`Could not run ${command}: ${error.message}`);
    process.exit(1);
  });
  child.on('exit', (code) => process.exit(code ?? 0));
}

/**
 * Backend with auto-restart on code changes.
 *
 * On Windows, `uvicorn --reload` restarts its worker by sending a Ctrl+C console event, and Windows
 * delivers that event to every process in the console, so npm quits and leaves the server orphaned.
 * Here we watch the files ourselves and restart uvicorn with a normal process stop instead, so no
 * console event is ever sent. Elsewhere uvicorn's own reloader works and is used.
 */
function serveBackend(args) {
  const uvicorn = ['-m', 'uvicorn', 'app.main:app', '--port', '8000', ...args];
  if (!isWindows) {
    serve(venvPython, [...uvicorn, '--reload'], backend);
    return;
  }
  process.on('SIGINT', () => {});
  let child;
  let restarting = false;
  let timer;
  const start = () => {
    child = spawn(venvPython, uvicorn, { cwd: backend, stdio: 'inherit' });
    child.on('exit', (code) => {
      if (restarting) {
        restarting = false;
        start();
      } else {
        process.exit(code ?? 0);
      }
    });
  };
  const restart = (file) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      console.log(`\nChange detected in ${file}. Restarting the backend...`);
      restarting = true;
      // .venv\Scripts\python.exe is a launcher that starts the real interpreter as a child process,
      // so stop the whole tree; killing only the launcher would leave the server holding port 8000.
      spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    }, 300);
  };
  watch(join(backend, 'app'), { recursive: true }, (_event, file) => {
    if (file && file.endsWith('.py')) restart(`app\\${file}`);
  });
  watch(backend, (_event, file) => {
    if (file === '.env') restart('.env');
  });
  console.log('Watching backend/app and backend/.env for changes.');
  start();
}

function requireVenv() {
  if (!existsSync(venvPython)) {
    console.error('The backend environment is not set up yet. Run: npm run setup');
    process.exit(1);
  }
}

function findSystemPython() {
  for (const candidate of isWindows ? ['py', 'python'] : ['python3', 'python']) {
    const check = spawnSync(candidate, ['--version'], { encoding: 'utf8' });
    if (check.status === 0 && /Python 3\.(1[2-9]|[2-9]\d)/.test(check.stdout + check.stderr)) return candidate;
  }
  console.error('Python 3.12 or newer was not found on PATH. Install it from https://www.python.org/downloads/');
  process.exit(1);
}

const [task, ...rest] = process.argv.slice(2);

switch (task) {
  case 'setup': {
    if (!existsSync(venvPython)) run(findSystemPython(), ['-m', 'venv', '.venv'], backend);
    run(venvPython, ['-m', 'pip', 'install', '-r', 'requirements-dev.txt'], backend);
    if (!existsSync(join(backend, '.env'))) {
      copyFileSync(join(backend, '.env.example'), join(backend, '.env'));
      console.log('Created backend/.env from .env.example. Set ALLOWED_EMAIL_DOMAINS to your campus domain.');
    }
    run(venvPython, ['-m', 'alembic', 'upgrade', 'head'], backend);
    run(venvPython, ['-m', 'app.db.seed'], backend);
    run('npm', ['install'], frontend);
    console.log('\nSetup complete. Start the backend with `npm run backend` and the frontend with `npm run frontend`.');
    break;
  }
  case 'backend':
    requireVenv();
    serveBackend(rest);
    break;
  case 'frontend':
    serve('npm', ['start', ...rest], frontend);
    break;
  case 'cli':
    requireVenv();
    run(venvPython, ['-m', 'app.cli', ...rest], backend);
    break;
  case 'test':
    requireVenv();
    run(venvPython, ['-m', 'pytest', ...rest], backend);
    run('npm', ['test', '--', '--watch=false'], frontend);
    break;
  default:
    console.log('Usage: npm run <setup|backend|frontend|test>, or npm run cli -- <command> [options]');
    process.exit(task ? 1 : 0);
}
