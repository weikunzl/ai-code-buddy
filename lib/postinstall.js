const { spawnSync } = require("child_process");
const path = require("path");
const { packageRoot } = require("./paths");

function main() {
  const root = packageRoot();
  const bridgeDir = path.join(root, "bridge");
  const result = spawnSync(
    "python3",
    ["-m", "pip", "install", "-e", bridgeDir],
    { stdio: "inherit", env: process.env },
  );
  if (result.status !== 0) {
    console.warn(
      "[devpet-cli] Could not pip-install bridge automatically.",
      "Run manually:",
      `python3 -m pip install -e ${bridgeDir}`,
    );
    process.exit(0);
  }
}

main();
