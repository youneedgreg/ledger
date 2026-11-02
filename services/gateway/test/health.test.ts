import { Writable } from "node:stream";
import { afterEach, describe, expect, it } from "vitest";
import { buildApp, loggerOptions } from "../src/app.js";

describe("gateway", () => {
  let app = buildApp();

  afterEach(async () => {
    await app.close();
    app = buildApp();
  });

  it("returns ok from /healthz", async () => {
    const response = await app.inject({ method: "GET", url: "/healthz" });

    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ status: "ok" });
  });

  it("generates a request ID", async () => {
    const response = await app.inject({ method: "GET", url: "/healthz" });

    expect(response.headers["request-id"]).toMatch(/^req_[0-9a-f-]{36}$/);
  });

  it("ignores a client-supplied request ID", async () => {
    const response = await app.inject({
      method: "GET",
      url: "/healthz",
      headers: { "request-id": "req_client-chosen" },
    });

    expect(response.headers["request-id"]).not.toBe("req_client-chosen");
  });

  it("logs JSON with the same field names as ledger-core", async () => {
    const lines: string[] = [];
    const stream = new Writable({
      write(chunk: Buffer, _encoding, done) {
        lines.push(chunk.toString());
        done();
      },
    });
    const logged = buildApp({ logger: { ...loggerOptions("info"), stream } });

    const response = await logged.inject({ method: "GET", url: "/healthz" });
    await logged.close();

    const entry = JSON.parse(lines[0] ?? "{}") as Record<string, unknown>;
    expect(entry).toMatchObject({
      level: "info",
      service: "gateway",
      request_id: response.headers["request-id"],
    });
    expect(entry).toHaveProperty("event");
    expect(entry).toHaveProperty("timestamp");
  });
});
