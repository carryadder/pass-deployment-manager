import { execSync } from "node:child_process";

execSync(
  "npx openapi --input http://127.0.0.1:8000/openapi.json --output src/api/generated --client fetch",
  { stdio: "inherit" },
);
