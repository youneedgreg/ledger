import { buildApp, loggerOptions } from "./app.js";
import { loadConfig } from "./config.js";

const config = loadConfig();
const app = buildApp({ logger: loggerOptions(config.LOG_LEVEL) });

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, () => {
    app.log.info({ signal }, "shutting down");
    app.close().then(
      () => process.exit(0),
      (error: unknown) => {
        app.log.error(error, "shutdown failed");
        process.exit(1);
      },
    );
  });
}

try {
  await app.listen({ host: config.HOST, port: config.PORT });
} catch (error) {
  app.log.fatal(error, "failed to start");
  process.exit(1);
}
