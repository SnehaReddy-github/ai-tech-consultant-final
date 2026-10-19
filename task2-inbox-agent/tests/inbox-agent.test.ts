import { afterEach, describe, expect, it, vi } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  classifyEmail,
  createDraft,
  type IncomingEmail,
} from "../src/inbox-agent.js";

import {
  InboxLearning,
  type DraftFeedback,
  type EmailKind,
} from "../src/learning.js";

const sampleEmail: IncomingEmail = {
  id: "email-001",
  from: "customer@example.com",
  subject: "Website error",
  body: "The website is not working and shows an error.",
};

const temporaryDirectories: string[] = [];

function createIsolatedLearning(): InboxLearning {
  const directory = mkdtempSync(join(tmpdir(), "inbox-agent-test-"));
  temporaryDirectories.push(directory);

  return new InboxLearning(join(directory, "feedback.json"));
}

function approvedFeedback(
  kind: EmailKind,
  number: number,
): DraftFeedback {
  const draft = "Hello, thank you for your email.";

  return {
    emailId: `email-${number}`,
    kind,
    originalDraft: draft,
    finalDraft: draft,
    approvedWithoutChanges: true,
    qualityScore: 1,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();

  while (temporaryDirectories.length > 0) {
    const directory = temporaryDirectories.pop();

    if (directory) {
      rmSync(directory, { recursive: true, force: true });
    }
  }
});

describe("Email classification", () => {
  it("classifies a technical issue as support", () => {
    expect(classifyEmail(sampleEmail).kind).toBe("support");
  });

  it("classifies a pricing enquiry", () => {
    expect(
      classifyEmail({
        ...sampleEmail,
        subject: "Pricing enquiry",
        body: "What is the price?",
      }).kind,
    ).toBe("pricing");
  });

  it("classifies a meeting request", () => {
    expect(
      classifyEmail({
        ...sampleEmail,
        subject: "Meeting request",
        body: "Can we schedule a meeting?",
      }).kind,
    ).toBe("meeting");
  });

  it("uses general when no category matches", () => {
    expect(
      classifyEmail({
        ...sampleEmail,
        subject: "Hello",
        body: "I wanted to share a quick update.",
      }).kind,
    ).toBe("general");
  });
});

describe("Draft generation", () => {
  it("creates a draft without sending an email", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Offline")));

    const result = await createDraft(sampleEmail);

    expect(result.emailId).toBe(sampleEmail.id);
    expect(result.kind).toBe("support");
    expect(result.draft.length).toBeGreaterThan(20);
    expect(result.needsHumanReview).toBe(true);
  });

  it("creates a draft for a pricing enquiry", async () => {
    const result = await createDraft({
      ...sampleEmail,
      subject: "Pricing",
      body: "Please share the price.",
    });

    expect(result.kind).toBe("pricing");
    expect(result.draft).toContain("pricing");
    expect(result.needsHumanReview).toBe(true);
  });

  it("uses Knowledge Brain results when available", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          answer: "Check your account settings.",
          sources: ["https://example.com/help"],
        }),
      }),
    );

    const result = await createDraft(sampleEmail);

    expect(result.draft).toContain("Check your account settings.");
    expect(result.sources).toContain("https://example.com/help");
  });

  it("falls back safely when the Knowledge Brain returns an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    const result = await createDraft(sampleEmail);

    expect(result.draft).toContain("reviewing the issue");
    expect(result.needsHumanReview).toBe(true);
  });
});

describe("Inbox learning and auto-send eligibility", () => {
  it("starts with human review required", () => {
    const learning = createIsolatedLearning();

    expect(learning.getStatus("support").enabled).toBe(false);
    expect(learning.getStatus("support").consecutiveUnchanged).toBe(0);
    expect(learning.isEligibleForAutoSend("support")).toBe(false);
  });

  it("does not enable eligibility before 20 unchanged approvals", () => {
    const learning = createIsolatedLearning();

    for (let i = 1; i <= 19; i++) {
      learning.recordFeedback(approvedFeedback("support", i));
    }

    expect(learning.getStatus("support").consecutiveUnchanged).toBe(19);
    expect(learning.getStatus("support").enabled).toBe(false);
    expect(learning.isEligibleForAutoSend("support")).toBe(false);
  });

  it("enables eligibility after 20 consecutive unchanged approvals", () => {
    const learning = createIsolatedLearning();

    for (let i = 1; i <= 20; i++) {
      learning.recordFeedback(approvedFeedback("support", i));
    }

    expect(learning.getStatus("support").consecutiveUnchanged).toBe(20);
    expect(learning.getStatus("support").enabled).toBe(true);
    expect(learning.isEligibleForAutoSend("support")).toBe(true);
  });

  it("resets the streak when a draft is edited", () => {
    const learning = createIsolatedLearning();

    for (let i = 1; i <= 5; i++) {
      learning.recordFeedback(approvedFeedback("sales", i));
    }

    const feedback = approvedFeedback("sales", 6);
    feedback.finalDraft = "Hello, I changed this reply.";
    feedback.approvedWithoutChanges = false;

    learning.recordFeedback(feedback);

    expect(learning.getStatus("sales").consecutiveUnchanged).toBe(0);
    expect(learning.getStatus("sales").enabled).toBe(false);
    expect(learning.isEligibleForAutoSend("sales")).toBe(false);
  });

  it("revokes eligibility when quality drops", () => {
    const learning = createIsolatedLearning();

    for (let i = 1; i <= 20; i++) {
      learning.recordFeedback(approvedFeedback("pricing", i));
    }

    expect(learning.isEligibleForAutoSend("pricing")).toBe(true);

    learning.recordFeedback({
      ...approvedFeedback("pricing", 21),
      qualityScore: 0.5,
    });

    expect(learning.getStatus("pricing").enabled).toBe(false);
    expect(learning.getStatus("pricing").consecutiveUnchanged).toBe(0);
    expect(learning.isEligibleForAutoSend("pricing")).toBe(false);
  });

  it("does not count a rejected draft as an unchanged approval", () => {
    const learning = createIsolatedLearning();
    const feedback = approvedFeedback("general", 1);

    feedback.approvedWithoutChanges = false;

    learning.recordFeedback(feedback);

    expect(learning.getStatus("general").consecutiveUnchanged).toBe(0);
    expect(learning.isEligibleForAutoSend("general")).toBe(false);
  });

  it("tracks each email kind separately", () => {
    const learning = createIsolatedLearning();

    for (let i = 1; i <= 20; i++) {
      learning.recordFeedback(approvedFeedback("support", i));
    }

    expect(learning.isEligibleForAutoSend("support")).toBe(true);
    expect(learning.isEligibleForAutoSend("sales")).toBe(false);
  });

  it("persists feedback across instances", () => {
    const directory = mkdtempSync(join(tmpdir(), "inbox-agent-persist-"));
    temporaryDirectories.push(directory);
    const filePath = join(directory, "feedback.json");

    const first = new InboxLearning(filePath);
    first.recordFeedback(approvedFeedback("meeting", 1));
    first.recordFeedback(approvedFeedback("meeting", 2));

    const restarted = new InboxLearning(filePath);

    expect(restarted.getFeedback()).toHaveLength(2);
    expect(restarted.getStatus("meeting").consecutiveUnchanged).toBe(2);
    expect(restarted.isEligibleForAutoSend("meeting")).toBe(false);
  });

  it("rejects an invalid quality score", () => {
    const learning = createIsolatedLearning();

    expect(() =>
      learning.recordFeedback({
        ...approvedFeedback("support", 1),
        qualityScore: 2,
      }),
    ).toThrow("Invalid feedback");
  });
});