
export type EmailKind = "support" | "pricing" | "sales" | "meeting" | "general";

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

interface KnowledgeResponse {
  answer?: string;
  sources?: string[];
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
  ],
  pricing: [
    "price",
    "pricing",
    "cost",
    "how much",
    "subscription fee",
    "plan options",
    "quote",
    "discount",
    "billing",
    "invoice",
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
];

export function classifyEmail(email: IncomingEmail): ClassificationResult {
  const text = `${email.subject} ${email.body}`.toLowerCase();
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
    return { kind: "general", confidence: 0.4 };
  }

  const confidence = Math.min(
    0.98,
    0.6 + (bestScore - secondScore) * 0.1,
  );

  return { kind: bestKind, confidence };
}

async function searchKnowledge(
  email: IncomingEmail,
): Promise<{ answer: string; sources: string[] }> {
  const baseUrl = (
    process.env.KNOWLEDGE_BRAIN_URL ?? "http://127.0.0.1:8001"
  ).replace(/\/+$/, "");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4000);

  try {
    const response = await fetch(`${baseUrl}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: `${email.subject}\n${email.body}`,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      return { answer: "", sources: [] };
    }

    const data = (await response.json()) as KnowledgeResponse;

    return {
      answer: typeof data.answer === "string" ? data.answer : "",
      sources: Array.isArray(data.sources)
        ? data.sources.filter(
            (source): source is string => typeof source === "string",
          )
        : [],
    };
  } catch {
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
        draft = knowledge.answer;
        sources = knowledge.sources;
      } else {
        draft =
        `Hello,\n\nThank you for contacting us about this issue. ` +
        `We are sorry for the inconvenience. Our team is reviewing ` +
        `the issue and will follow up with you.\n\nBest regards,\nSupport Team`;
      }
      break;
    }

    case "pricing":
      draft =
        `Hello,\n\nThank you for your interest in our pricing. ` +
        `We would be happy to help you understand the available plans ` +
        `and pricing options. Please share any specific requirements ` +
        `so our team can guide you.\n\nBest regards,\nSales Team`;
      break;

    case "sales":
      draft =
        `Hello,\n\nThank you for your interest in our solutions. ` +
        `We would be happy to learn more about your requirements and ` +
        `discuss how we may be able to help.\n\nBest regards,\nSales Team`;
      break;

    case "meeting":
      draft =
        `Hello,\n\nThank you for reaching out. We would be happy to ` +
        `arrange a meeting. Please share your preferred date and time, ` +
        `and we will confirm availability.\n\nBest regards,\nTeam`;
      break;

    case "general":
    default:
      draft =
        `Hello,\n\nThank you for your email. We appreciate you reaching ` +
        `out and will review your message. Our team will follow up ` +
        `if any further information is needed.\n\nBest regards,\nTeam`;
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
