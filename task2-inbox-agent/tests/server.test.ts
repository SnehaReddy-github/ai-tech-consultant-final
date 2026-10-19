import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createServer, type Server } from "node:http";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createApp } from "../src/server.js";
import { InboxLearning, type EmailKind } from "../src/learning.js";

describe("Inbox Agent HTTP review API", () => {
  let server: Server;
  let baseUrl: string;
  let temporaryDirectory: string;

  beforeEach(async () => {
    temporaryDirectory = mkdtempSync(join(tmpdir(), "inbox-review-test-"));

    const learning = new InboxLearning(
      join(temporaryDirectory, "feedback.json"),
    );
    const app = createApp(learning);

    server = createServer(app);

    await new Promise<void>((resolve, reject) => {
      server.once("error", reject);
      server.listen(0, "127.0.0.1", () => {
        server.removeListener("error", reject);
        const address = server.address();

        if (!address || typeof address === "string") {
          reject(new Error("Could not determine the test server address."));
          return;
        }

        baseUrl = `http://127.0.0.1:${address.port}`;
        resolve();
      });
    });
  });

  afterEach(async () => {
    if (server?.listening) {
      await new Promise<void>((resolve, reject) => {
        server.close((error) => {
          if (error) reject(error);
          else resolve();
        });
      });
    }

    if (temporaryDirectory) {
      rmSync(temporaryDirectory, { recursive: true, force: true });
    }
  });

  async function submitReview(payload: Record<string, unknown>) {
    return fetch(`${baseUrl}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  function reviewPayload(overrides: Record<string, unknown> = {}) {
    return {
      emailId: "review-email-1",
      kind: "pricing" as EmailKind,
      originalDraft: "Hello, thank you for your enquiry.",
      finalDraft: "Hello, thank you for your enquiry.",
      decision: "approved",
      qualityScore: 0.95,
      ...overrides,
    };
  }

  it("records an unchanged approval without sending an email", async () => {
    const response = await submitReview(reviewPayload());
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.decision).toBe("approved");
    expect(data.approvedWithoutChanges).toBe(true);
    expect(data.learningStatus.consecutiveUnchanged).toBe(1);
    expect(data.autoSendExecuted).toBe(false);
  });

  it("resets the approval streak when the approved draft was edited", async () => {
    for (let i = 0; i < 3; i++) {
      await submitReview(reviewPayload({ emailId: `approved-${i}` }));
    }

    const response = await submitReview(
      reviewPayload({
        emailId: "edited-1",
        finalDraft: "Hello, thanks for contacting our team.",
      }),
    );
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.approvedWithoutChanges).toBe(false);
    expect(data.learningStatus.consecutiveUnchanged).toBe(0);
    expect(data.learningStatus.enabled).toBe(false);
    expect(data.autoSendExecuted).toBe(false);
  });

  it("does not count a rejected draft as an unchanged approval", async () => {
    const response = await submitReview(
      reviewPayload({ decision: "rejected" }),
    );
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.decision).toBe("rejected");
    expect(data.approvedWithoutChanges).toBe(false);
    expect(data.learningStatus.consecutiveUnchanged).toBe(0);
    expect(data.autoSendExecuted).toBe(false);
  });

  it("rejects an invalid quality score", async () => {
    const response = await submitReview(
      reviewPayload({ qualityScore: 1.5 }),
    );

    expect(response.status).toBe(400);
  });

  it("rejects an unknown email category", async () => {
    const response = await submitReview(
      reviewPayload({ kind: "unknown" }),
    );

    expect(response.status).toBe(400);
  });

  it("rejects an unsupported review decision", async () => {
    const response = await submitReview(
      reviewPayload({ decision: "maybe" }),
    );

    expect(response.status).toBe(400);
  });

  it("revokes eligibility after low-quality feedback", async () => {
    for (let i = 1; i <= 20; i++) {
      const response = await submitReview(
        reviewPayload({ emailId: `quality-${i}` }),
      );

      expect(response.status).toBe(200);
    }

    const lowQualityResponse = await submitReview(
      reviewPayload({
        emailId: "quality-drop",
        qualityScore: 0.4,
      }),
    );
    const data = await lowQualityResponse.json();

    expect(data.learningStatus.enabled).toBe(false);
    expect(data.learningStatus.consecutiveUnchanged).toBe(0);
    expect(data.autoSendExecuted).toBe(false);
  });

  it("returns a health response", async () => {
    const response = await fetch(`${baseUrl}/health`);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
  });
});
