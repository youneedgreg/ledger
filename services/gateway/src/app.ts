import { randomUUID } from "node:crypto";
import Fastify, {
  type FastifyInstance,
  type FastifyServerOptions,
  LogController,
} from "fastify";

export const SERVICE_NAME = "gateway";

type LoggerOptions = Exclude<FastifyServerOptions["logger"], boolean | undefined>;

// Same field names as ledger-core, so logs from both services can be queried together.
export function loggerOptions(level: string): LoggerOptions {
  return {
    level,
    messageKey: "event",
    base: { service: SERVICE_NAME },
    timestamp: () => `,"timestamp":"${new Date().toISOString()}"`,
    formatters: {
      level: (label: string) => ({ level: label }),
    },
  };
}

export interface BuildOptions {
  logger?: FastifyServerOptions["logger"];
}

export function buildApp(options: BuildOptions = {}): FastifyInstance {
  const app = Fastify({
    logger: options.logger ?? false,
    // This is the public edge, so client-supplied IDs are ignored.
    requestIdHeader: false,
    logController: new LogController({ requestIdLogLabel: "request_id" }),
    genReqId: () => `req_${randomUUID()}`,
  });

  app.addHook("onRequest", (request, reply, done) => {
    void reply.header("Request-Id", request.id);
    done();
  });

  // Liveness: the process is up. Doesn't call the core.
  app.get("/healthz", () => ({ status: "ok" }));

  return app;
}
