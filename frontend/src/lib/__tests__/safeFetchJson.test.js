/**
 * iter 325v — safeFetchJson defensive-parse contract tests.
 *
 * These prove that the production "Unexpected token '<', '<!DOCTYPE '"
 * crash mode can no longer reach the React render path.
 */
import { safeFetchJson } from "../safeFetchJson";

function mockFetch(impl) {
  global.fetch = jest.fn().mockImplementation(impl);
}

function htmlResponse(status, body = "<!DOCTYPE html><html>error</html>") {
  return Promise.resolve({
    status,
    ok: status >= 200 && status < 300,
    headers: { get: () => "text/html; charset=UTF-8" },
    json: () => Promise.reject(new Error("Unexpected token '<', \"<!DOCTYPE \" is not valid JSON")),
    text: () => Promise.resolve(body),
  });
}

function jsonResponse(status, body) {
  return Promise.resolve({
    status,
    ok: status >= 200 && status < 300,
    headers: { get: () => "application/json" },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });
}

describe("safeFetchJson (iter 325v root-cause defence)", () => {
  test("Cloudflare 520 HTML response → friendly gateway error, never throws", async () => {
    mockFetch(() => htmlResponse(520));
    const r = await safeFetchJson("/api/admin/ora-dev/list");
    expect(r.ok).toBe(false);
    expect(r.isGatewayError).toBe(true);
    expect(r.error).toMatch(/non-JSON|origin/i);
    expect(r.error).not.toMatch(/Unexpected token/);
  });

  test("401 with JSON body → isAuthError true", async () => {
    mockFetch(() => jsonResponse(401, { detail: "Missing token" }));
    const r = await safeFetchJson("/api/admin/ora-dev/list");
    expect(r.ok).toBe(false);
    expect(r.isAuthError).toBe(true);
    expect(r.isGatewayError).toBe(false);
  });

  test("Network drop → friendly gateway error", async () => {
    mockFetch(() => Promise.reject(new Error("Failed to fetch")));
    const r = await safeFetchJson("/api/admin/ora-dev/list");
    expect(r.ok).toBe(false);
    expect(r.isGatewayError).toBe(true);
  });

  test("200 OK with JSON → success path", async () => {
    mockFetch(() => jsonResponse(200, { items: [1, 2, 3] }));
    const r = await safeFetchJson("/api/admin/ora-dev/list");
    expect(r.ok).toBe(true);
    expect(r.data.items).toEqual([1, 2, 3]);
  });

  test("HTML 200 (wrong content-type) → friendly error, no throw", async () => {
    mockFetch(() => htmlResponse(200));
    const r = await safeFetchJson("/api/foo");
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/non-JSON|Unexpected text\/html/i);
  });
});
