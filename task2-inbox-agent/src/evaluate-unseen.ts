
import { classifyEmail, type IncomingEmail } from "./inbox-agent.js";

const unseenEmails: Array<{
  email: IncomingEmail;
  expectedKind: "support" | "pricing" | "sales" | "meeting" | "general";
}> = [
  {
    email: {
      id: "U001",
      from: "client@example.com",
      subject: "Unable to access my account",
      body: "I enter my password, but the application keeps rejecting it.",
    },
    expectedKind: "support",
  },
  {
    email: {
      id: "U002",
      from: "buyer@example.com",
      subject: "Annual subscription estimate",
      body: "Could you send the total yearly cost for five users?",
    },
    expectedKind: "pricing",
  },
  {
    email: {
      id: "U003",
      from: "prospect@example.com",
      subject: "Interested in your platform",
      body: "We are evaluating solutions for our company and would like a demonstration.",
    },
    expectedKind: "sales",
  },
  {
    email: {
      id: "U004",
      from: "colleague@example.com",
      subject: "Move our discussion",
      body: "Can we reschedule our call for another day?",
    },
    expectedKind: "meeting",
  },
  {
    email: {
      id: "U005",
      from: "customer@example.com",
      subject: "Thank you",
      body: "Thank you for sending the information yesterday.",
    },
    expectedKind: "general",
  },
  {
    email: {
      id: "U006",
      from: "client@example.com",
      subject: "Export problem",
      body: "The export button returns an error and no file is downloaded.",
    },
    expectedKind: "support",
  },
  {
    email: {
      id: "U007",
      from: "finance@example.com",
      subject: "Invoice clarification",
      body: "Please explain the additional charges on our latest invoice.",
    },
    expectedKind: "pricing",
  },
  {
    email: {
      id: "U008",
      from: "partner@example.com",
      subject: "Potential collaboration",
      body: "We would like to discuss a partnership between our businesses.",
    },
    expectedKind: "sales",
  },
  {
    email: {
      id: "U009",
      from: "team@example.com",
      subject: "Tomorrow's appointment",
      body: "Please send the calendar invitation and joining details.",
    },
    expectedKind: "meeting",
  },
  {
    email: {
      id: "U010",
      from: "person@example.com",
      subject: "General question",
      body: "Who should I contact about an unrelated administrative question?",
    },
    expectedKind: "general",
  },
  {
    email: {
      id: "U011",
      from: "customer@example.com",
      subject: "Dashboard issue and renewal",
      body: "The dashboard is broken, and I also need to know the renewal cost.",
    },
    expectedKind: "support",
  },
  {
    email: {
      id: "U012",
      from: "lead@example.com",
      subject: "Can we talk?",
      body: "I would like to learn about your product and arrange a demo next week.",
    },
    expectedKind: "sales",
  },
];

let correct = 0;

console.log(`Evaluating ${unseenEmails.length} unseen emails...\n`);

for (const item of unseenEmails) {
  const result = classifyEmail(item.email);
  const passed = result.kind === item.expectedKind;

  if (passed) correct++;

  console.log(
    `${passed ? "PASS" : "FAIL"} ${item.email.id}: ` +
      `expected=${item.expectedKind}, predicted=${result.kind}, ` +
      `subject="${item.email.subject}"`,
  );
}

const accuracy = (correct / unseenEmails.length) * 100;

console.log("\n========== UNSEEN EMAIL RESULTS ==========");
console.log(`Total emails: ${unseenEmails.length}`);
console.log(`Correct: ${correct}`);
console.log(`Incorrect: ${unseenEmails.length - correct}`);
console.log(`Accuracy: ${accuracy.toFixed(2)}%`);
