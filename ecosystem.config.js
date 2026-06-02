// PM2 process config for forge-api.
// Secrets loaded from .env at startup — never commit .env to git.
const fs = require("fs");
const path = require("path");

function loadEnv(file) {
  try {
    return Object.fromEntries(
      fs.readFileSync(file, "utf8")
        .split("\n")
        .filter(l => l && !l.startsWith("#") && l.includes("="))
        .map(l => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
    );
  } catch {
    return {};
  }
}

const env = loadEnv(path.join(__dirname, ".env"));

module.exports = {
  apps: [
    {
      name: "forge-api",
      script: "bash",
      args: "-c 'uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info'",
      cwd: __dirname,
      env: {
        ...env,
        SPECS_DIR: path.join(__dirname, "data/specs"),
      },
      max_restarts: 10,
      restart_delay: 3000,
      max_memory_restart: "512M",
    },
  ],
};
