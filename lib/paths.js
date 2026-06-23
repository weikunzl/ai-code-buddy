const path = require("path");

/** Root of the installed devpet-cli package (contains bridge/, hooks/, tools/). */
function packageRoot() {
  return path.resolve(__dirname, "..");
}

module.exports = { packageRoot };
