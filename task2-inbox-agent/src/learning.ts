import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { dirname, resolve } from "node:path";

export type EmailKind =
  | "support"
  | "pricing"
  | "sales"
  | "meeting"
  | "general";

export interface DraftFeedback {
  emailId: string;
  kind: EmailKind;
  originalDraft: string;
  finalDraft: string;
  approvedWithoutChanges: boolean;
  qualityScore: number;
}

export interface AutoSendStatus {
  kind: EmailKind;
  consecutiveUnchanged: number;
  enabled: boolean;
  reason: string;
}

const REQUIRED_UNCHANGED_DRAFTS = 20;
const MINIMUM_QUALITY_SCORE = 0.8;

const VALID_KINDS: EmailKind[] = [
  "support",
  "pricing",
  "sales",
  "meeting",
  "general",
];

const DEFAULT_FEEDBACK_PATH = resolve("data", "feedback.json");

function isFeedback(value: unknown): value is DraftFeedback {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const item = value as Record<string, unknown>;

  return (
    typeof item.emailId === "string" &&
    item.emailId.trim().length > 0 &&
    VALID_KINDS.includes(item.kind as EmailKind) &&
    typeof item.originalDraft === "string" &&
    typeof item.finalDraft === "string" &&
    typeof item.approvedWithoutChanges === "boolean" &&
    typeof item.qualityScore === "number" &&
    Number.isFinite(item.qualityScore) &&
    item.qualityScore >= 0 &&
    item.qualityScore <= 1
  );
}

export class InboxLearning {
  private feedback: DraftFeedback[] = [];
  private status = new Map<EmailKind, AutoSendStatus>();

  constructor(
    private readonly feedbackPath: string = DEFAULT_FEEDBACK_PATH,
  ) {
    this.loadFeedback();
  }

  private loadFeedback(): void {
    if (!existsSync(this.feedbackPath)) {
      return;
    }

    try {
      const parsed: unknown = JSON.parse(
        readFileSync(this.feedbackPath, "utf8"),
      );

      if (!Array.isArray(parsed) || !parsed.every(isFeedback)) {
        console.warn(
          "Feedback file has an invalid format. Starting with empty learning data.",
        );
        return;
      }

      for (const item of parsed) {
        this.applyFeedback(item, false);
      }
    } catch {
      console.warn(
        "Could not read the feedback file. Starting with empty learning data.",
      );
    }
  }

  private saveFeedback(): void {
    mkdirSync(dirname(this.feedbackPath), { recursive: true });

    writeFileSync(
      this.feedbackPath,
      JSON.stringify(this.feedback, null, 2),
      "utf8",
    );
  }

  private applyFeedback(
    feedback: DraftFeedback,
    persist: boolean,
  ): AutoSendStatus {
    this.feedback.push({ ...feedback });

    const previous = this.getStatus(feedback.kind);
    let next: AutoSendStatus;

    if (feedback.qualityScore < MINIMUM_QUALITY_SCORE) {
      next = {
        kind: feedback.kind,
        consecutiveUnchanged: 0,
        enabled: false,
        reason:
          "Quality fell below the threshold. Human review is required.",
      };
    } else if (
      !feedback.approvedWithoutChanges ||
      feedback.originalDraft !== feedback.finalDraft
    ) {
      next = {
        kind: feedback.kind,
        consecutiveUnchanged: 0,
        enabled: false,
        reason:
          "The draft was edited or not approved unchanged. The approval streak was reset.",
      };
    } else {
      const count = previous.consecutiveUnchanged + 1;
      const enabled = count >= REQUIRED_UNCHANGED_DRAFTS;

      next = {
        kind: feedback.kind,
        consecutiveUnchanged: count,
        enabled,
        reason: enabled
          ? "Threshold reached. Eligible for auto-send review, but no email is sent automatically."
          : `${REQUIRED_UNCHANGED_DRAFTS - count} more unchanged approvals required.`,
      };
    }

    this.status.set(feedback.kind, next);

    if (persist) {
      this.saveFeedback();
    }

    return { ...next };
  }

  recordFeedback(feedback: DraftFeedback): AutoSendStatus {
    if (!isFeedback(feedback)) {
      throw new Error(
        "Invalid feedback. Check the email ID, kind, draft texts, approval flag, and quality score.",
      );
    }

    return this.applyFeedback(feedback, true);
  }

  getStatus(kind: EmailKind): AutoSendStatus {
    const existing = this.status.get(kind);

    if (existing) {
      return { ...existing };
    }

    return {
      kind,
      consecutiveUnchanged: 0,
      enabled: false,
      reason:
        "Human approval is required until the learning threshold is met.",
    };
  }

  getFeedback(): DraftFeedback[] {
    return this.feedback.map((item) => ({ ...item }));
  }

  isEligibleForAutoSend(kind: EmailKind): boolean {
    return this.getStatus(kind).enabled;
  }
}