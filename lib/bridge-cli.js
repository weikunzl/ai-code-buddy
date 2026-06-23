const { spawnSync } = require("child_process");
const path = require("path");
const { packageRoot } = require("./paths");

function packageEnv() {
  const root = packageRoot();
  return {
    ...process.env,
    DEVPET_PACKAGE_ROOT: root,
    PYTHONPATH: [root, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
  };
}

function runScript(scriptName, args = []) {
  const root = packageRoot();
  const script = path.join(root, "tools", scriptName);
  const result = spawnSync("bash", [script, ...args], {
    cwd: root,
    env: packageEnv(),
    stdio: "inherit",
  });
  if (result.error) {
    console.error(`[devpet-bridge] failed to run ${scriptName}:`, result.error.message);
    process.exit(1);
  }
  process.exit(result.status ?? 1);
}

function runPythonModule(args) {
  const root = packageRoot();
  const result = spawnSync("python3", ["-m", "bridge", ...args], {
    cwd: root,
    env: packageEnv(),
    stdio: "inherit",
  });
  if (result.error) {
    console.error("[devpet-bridge] python3 not found or bridge module missing:", result.error.message);
    console.error("Try: python3 -m pip install -e", path.join(root, "bridge"));
    process.exit(1);
  }
  process.exit(result.status ?? 1);
}

function printHelp() {
  const root = packageRoot();
  console.log(`devpet-cli — DevPet session bridge launcher

Usage:
  devpet-bridge restart          Kill stale listeners, start HTTP :9876 + WS :9877
  devpet-bridge start            Start only if ports are free
  devpet-bridge run [args...]    Run python3 -m bridge (pass-through flags)

Environment:
  BUDDY_HTTP_PORT   HTTP hook port (default 9876)
  BUDDY_WS_PORT     WebSocket port for phone (default 9877)

Package root: ${root}

Install:
  npm install -g github:weikunzl/ai-code-buddy

From a git clone you can still use:
  ./tools/restart_bridge.sh
  ./tools/start_bridge.sh
`);
}

function main(argv) {
  const sub = argv[0] || "help";

  if (sub === "help" || sub === "-h" || sub === "--help") {
    printHelp();
    process.exit(0);
  }

  if (sub === "restart") {
    runScript("restart_bridge.sh");
  }

  if (sub === "start") {
    runScript("start_bridge.sh");
  }

  if (sub === "run") {
    runPythonModule(argv.slice(1));
  }

  console.error(`[devpet-bridge] unknown command: ${sub}`);
  printHelp();
  process.exit(1);
}

module.exports = { main, packageEnv, packageRoot };
