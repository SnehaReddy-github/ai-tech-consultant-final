import express from "express";
import { createDraft, type IncomingEmail } from "./inbox-agent.js";
import {
  InboxLearning,
  type DraftFeedback,
  type EmailKind,
} from "./learning.js";

const PORT = Number(process.env.PORT ?? 3001);

const EMAIL_KINDS: EmailKind[] = [
  "support",
  "pricing",
  "sales",
  "meeting",
  "general",
];

export function createApp(learning = new InboxLearning()) {
  const app = express();

  app.use(express.json({ limit: "1mb" }));

  app.get("/", (_req, res) => {
    res.json({
      name: "AI Tech Consultant - Inbox Agent",
      status: "running",
      mode: "local-demo",
      endpoints: [
        "/health",
        "/classify-and-draft",
        "/review",
        "/feedback",
        "/learning-status/:kind",
      ],
    });
  });

  app.get("/health", (_req, res) => {
    res.json({ status: "ok" });
  });

  app.post("/classify-and-draft", async (req, res) => {
    const email = req.body as Partial<IncomingEmail>;

    if (
      typeof email?.id !== "string" ||
      typeof email.from !== "string" ||
      typeof email.subject !== "string" ||
      typeof email.body !== "string" ||
      !email.id.trim() ||
      !email.from.trim() ||
      !email.subject.trim() ||
      !email.body.trim()
    ) {
      res.status(400).json({
        error: "Provide non-empty string fields: id, from, subject, body.",
      });
      return;
    }

    try {
      const result = await createDraft(email as IncomingEmail);
      const status = learning.getStatus(result.kind);

      res.json({
        ...result,
        autoSendEligible: status.enabled,
        autoSendExecuted: false,
        message: "Draft created for review. No email has been sent.",
      });
    } catch {
      res.status(500).json({
        error: "Could not create the email draft.",
      });
    }
  });

  app.post("/review", (req, res) => {
    const {
      emailId,
      kind,
      originalDraft,
      finalDraft,
      decision,
      qualityScore,
    } = req.body ?? {};

    if (
      typeof emailId !== "string" ||
      !emailId.trim() ||
      !EMAIL_KINDS.includes(kind as EmailKind) ||
      typeof originalDraft !== "string" ||
      typeof finalDraft !== "string" ||
      !["approved", "rejected"].includes(decision) ||
      typeof qualityScore !== "number" ||
      !Number.isFinite(qualityScore) ||
      qualityScore < 0 ||
      qualityScore > 1
    ) {
      res.status(400).json({
        error:
          "Provide emailId, valid kind, originalDraft, finalDraft, decision (approved or rejected), and qualityScore between 0 and 1.",
      });
      return;
    }

    const feedback: DraftFeedback = {
      emailId,
      kind: kind as EmailKind,
      originalDraft,
      finalDraft,
      approvedWithoutChanges:
        decision === "approved" && originalDraft === finalDraft,
      qualityScore,
    };

    try {
      const status = learning.recordFeedback(feedback);

      res.json({
        message: "Human review recorded. No email has been sent.",
        decision,
        approvedWithoutChanges: feedback.approvedWithoutChanges,
        learningStatus: status,
        autoSendExecuted: false,
      });
    } catch {
      res.status(400).json({
        error: "Could not record review feedback.",
      });
    }
  });

  app.post("/feedback", (req, res) => {
    const feedback = req.body as Partial<DraftFeedback>;

    if (
      typeof feedback?.emailId !== "string" ||
      !feedback.emailId.trim() ||
      !EMAIL_KINDS.includes(feedback.kind as EmailKind) ||
      typeof feedback.originalDraft !== "string" ||
      typeof feedback.finalDraft !== "string" ||
      typeof feedback.approvedWithoutChanges !== "boolean" ||
      typeof feedback.qualityScore !== "number" ||
      !Number.isFinite(feedback.qualityScore) ||
      feedback.qualityScore < 0 ||
      feedback.qualityScore > 1
    ) {
      res.status(400).json({
        error: "Invalid feedback. qualityScore must be between 0 and 1.",
      });
      return;
    }

    try {
      const status = learning.recordFeedback(feedback as DraftFeedback);

      res.json({
        message: "Feedback recorded. No email has been sent.",
        learningStatus: status,
        autoSendExecuted: false,
      });
    } catch {
      res.status(400).json({
        error: "Could not record feedback.",
      });
    }
  });

  app.get("/learning-status/:kind", (req, res) => {
    const kind = req.params.kind;

    if (!EMAIL_KINDS.includes(kind as EmailKind)) {
      res.status(400).json({ error: "Unknown email kind." });
      return;
    }

    res.json(learning.getStatus(kind as EmailKind));
  });

  return app;
}

export const app = createApp();

// Only start listening when this file is executed directly by `npm start`.
// Importing it in tests does not open a network port.
if (process.argv[1]?.replace(/\\/g, "/").endsWith("/src/server.ts")) {
  app.listen(PORT, () => {
    console.log(`Inbox Agent running at http://127.0.0.1:${PORT}`);
  });
}
