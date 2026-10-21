
export type EmailKind =
  | "support"
  | "pricing"
  | "sales"
  | "meeting"
  | "general";

export interface IncomingEmail {
  id: string;
  from: string;
  subject: string;
  body: string;
}

export interface ClassificationResult {
  kind: EmailKind;
  confidence: number;
}

export interface DraftResult {
  emailId: string;
  kind: EmailKind;
  confidence: number;
  draft: string;
  sources: string[];
  needsHumanReview: boolean;
}

interface KnowledgeSource {
  id?: number;
  title?: string;
  url?: string;
}

interface KnowledgeResponse {
  answer?: string;
  sources?: Array<string | KnowledgeSource>;
  status?: string;
  needs_human_review?: boolean;
  mode?: string;
}

const RULES: Record<Exclude<EmailKind, "general">, string[]> = {
  support: [
    "not working",
    "does not work",
    "doesn't work",
    "error",
    "bug",
    "broken",
    "issue",
    "problem",
    "unable to access",
    "access my account",
    "reports are not loading",
    "feature appears unavailable",
    "account access issue",
    "dashboard is broken",
    "dashboard issue",
    "technical issue",
    "cannot log in",
    "can't log in",
    "login problem",
    "not loading",
    "failed to load",
    "fails",
    "failure",
    "expired",
    "password reset",
    "incorrect totals",
    "notifications stopped",
    "duplicate records",
    "application closes",
    "slow page",
    "export",
    "import",
    "stopped arriving",
    "download fails",
    "access problem",
    "trouble accessing",
    "keeps crashing",
    "doesn't load",
    "manage member accounts",
    "member account",
    "manage members",
    "account management",
    "how do i manage",
    "how to manage member",
    "change my account email",
    "change account email",
    "update my account email",
    "change email address",
    "update email address",
  ],

  pricing: [
    "price",
    "pricing",
    "cost",
    "how much",
    "subscription fee",
    "plan options",
    "quote",
    "quotation",
    "discount",
    "billing",
    "invoice",
    "free plan",
    "subscription",
    "renewal",
    "additional charges",
    "yearly cost",
    "annual cost",
    "revised quotation",
    "payment",
    "upgrade cost",
  ],

  sales: [
    "interested in your product",
    "purchase",
    "buy",
    "demo",
    "sales enquiry",
    "sales inquiry",
    "product information",
    "sign up",
    "business partnership",
    "partnership opportunity",
    "evaluating your solution",
    "product brochure",
    "partner enquiry",
    "partner inquiry",
    "potential collaboration",
    "collaboration",
    "procurement",
    "interested in upgrading",
    "learn about your product",
    "product demonstration",
    "business requirements",
    "interested in your platform",
    "solution for our company",
    "does your platform support",
    "support our use case",
    "platform support our use case",
  ],

  meeting: [
    "meeting",
    "schedule a call",
    "book a call",
    "calendar",
    "appointment",
    "available tomorrow",
    "discuss this",
    "let's talk",
    "lets talk",
    "reschedule",
    "discovery call",
    "project review",
    "set up a call",
    "arrange a call",
    "short call",
    "schedule a meeting",
    "move our discussion",
    "joining details",
    "calendar invitation",
  ],
};

const STRONG_SUPPORT_PHRASES = [
  "reports are not loading",
  "feature appears unavailable",
  "unable to access my account",
  "unable to access",
  "account access issue",
  "dashboard is broken",
  "dashboard issue",
  "technical issue",
  "password reset",
  "csv export",
  "export fails",
  "export problem",
  "application closes",
  "duplicate records",
  "notifications stopped",
  "manage member accounts",
  "member account",
  "manage members",
  "account management",
  "how do i manage",
  "how to manage member",
  "change my account email",
  "change account email",
  "update my account email",
  "change email address",
  "update email address",
];

export function classifyEmail(
  email: IncomingEmail,
): ClassificationResult {
  const text = `${email.subject} ${email.body}`.toLowerCase();

  // Explicit general-question rule to avoid false sales classifications.
  if (
    text.includes("general question") ||
    text.includes("general inquiry") ||
    text.includes("general enquiry")
  ) {
    return {
      kind: "general",
      confidence: 0.9,
    };
  }

  const scores: Record<EmailKind, number> = {
    support: 0,
    pricing: 0,
    sales: 0,
    meeting: 0,
    general: 0,
  };

  for (const [kind, phrases] of Object.entries(RULES) as [
    Exclude<EmailKind, "general">,
    string[],
  ][]) {
    for (const phrase of phrases) {
      if (text.includes(phrase)) {
        scores[kind] += 1;
      }
    }
  }

  for (const phrase of STRONG_SUPPORT_PHRASES) {
    if (text.includes(phrase)) {
      scores.support += 3;
    }
  }

  const ranked = (
    Object.entries(scores) as [EmailKind, number][]
  ).sort((a, b) => b[1] - a[1]);

  const [bestKind, bestScore] = ranked[0];
  const secondScore = ranked[1][1];

  if (bestScore === 0 || bestScore === secondScore) {
    return {
      kind: "general",
      confidence: 0.4,
    };
  }

  return {
    kind: bestKind,
    confidence: Math.min(
      0.98,
      0.6 + (bestScore - secondScore) * 0.1,
    ),
  };
}

async function searchKnowledge(
  email: IncomingEmail,
): Promise<{ answer: string; sources: string[] }> {
  const baseUrl = (
    process.env.KNOWLEDGE_BRAIN_URL ??
    "http://127.0.0.1:8002"
  ).replace(/\/+$/, "");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);

  try {
    const response = await fetch(`${baseUrl}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question: `${email.subject}\n${email.body}`,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      console.error(
        `Knowledge Brain returned HTTP ${response.status}`,
      );
      return { answer: "", sources: [] };
    }

    const data = (await response.json()) as KnowledgeResponse;

    const answer =
      typeof data.answer === "string" &&
      data.status !== "not_found"
        ? data.answer
        : "";

    const sources = Array.isArray(data.sources)
      ? data.sources
          .map((source) => {
            if (
              typeof source === "string" &&
              source.trim().length > 0
            ) {
              return source;
            }

            if (
              typeof source === "object" &&
              source !== null &&
              typeof source.url === "string" &&
              source.url.trim().length > 0
            ) {
              return `${source.title ?? "Knowledge source"}: ${source.url}`;
            }

            return "";
          })
          .filter((source) => source.length > 0)
      : [];

    return { answer, sources };
  } catch (error) {
    console.error(
      "Knowledge Brain request failed:",
      error instanceof Error ? error.message : error,
    );

    return { answer: "", sources: [] };
  } finally {
    clearTimeout(timeout);
  }
}

export async function createDraft(
  email: IncomingEmail,
): Promise<DraftResult> {
  const classification = classifyEmail(email);
  const kind = classification.kind;

  let draft: string;
  let sources: string[] = [];

  switch (kind) {
    case "support": {
      const knowledge = await searchKnowledge(email);

      if (knowledge.answer && knowledge.sources.length > 0) {
        draft =
          `Hello,\n\n` +
          `Thank you for contacting our support team.\n\n` +
          `${knowledge.answer}\n\n` +
          `Please review the linked knowledge sources for details.\n\n` +
          `Best regards,\nSupport Team`;

        sources = knowledge.sources;
      } else {
        draft =
          `Hello,\n\n` +
          `Thank you for contacting us about this issue. ` +
          `We are sorry for the inconvenience. Our team is reviewing ` +
          `the issue and will follow up with you.\n\n` +
          `Best regards,\nSupport Team`;
      }
      break;
    }

    case "pricing":
      draft =
        `Hello,\n\n` +
        `Thank you for your interest in our pricing. ` +
        `We would be happy to help you understand the available plans ` +
        `and pricing options. Please share any specific requirements ` +
        `so our team can guide you.\n\n` +
        `Best regards,\nSales Team`;
      break;

    case "sales":
      draft =
        `Hello,\n\n` +
        `Thank you for your interest in our solutions. ` +
        `We would be happy to learn more about your requirements and ` +
        `discuss how we may be able to help.\n\n` +
        `Best regards,\nSales Team`;
      break;

    case "meeting":
      draft =
        `Hello,\n\n` +
        `Thank you for reaching out. We would be happy to ` +
        `arrange a meeting. Please share your preferred date and time, ` +
        `and we will confirm availability.\n\n` +
        `Best regards,\nTeam`;
      break;

    case "general":
    default:
      draft =
        `Hello,\n\n` +
        `Thank you for your email. We appreciate you reaching ` +
        `out and will review your message. Our team will follow up ` +
        `if any further information is needed.\n\n` +
        `Best regards,\nTeam`;
      break;
  }

  return {
    emailId: email.id,
    kind,
    confidence: classification.confidence,
    draft,
    sources,
    needsHumanReview: true,
  };
}
