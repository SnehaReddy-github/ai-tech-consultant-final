
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { classifyEmail, type IncomingEmail } from "./inbox-agent.js";

interface DatasetEmail extends IncomingEmail {
  expectedKind: "support" | "pricing" | "sales" | "meeting" | "general";
}

interface EmailDataset {
  emails: DatasetEmail[];
}

const datasetPath = resolve("task2-inbox-agent", "data", "sample-emails.json");
const dataset = JSON.parse(
  readFileSync(datasetPath, "utf8"),
) as EmailDataset;

if (!Array.isArray(dataset.emails) || dataset.emails.length === 0) {
  throw new Error("Dataset is empty or has an invalid format.");
}

const categories = ["support", "pricing", "sales", "meeting", "general"];
let correct = 0;
const confusion: Record<string, Record<string, number>> = {};

for (const category of categories) {
  confusion[category] = {};
  for (const predicted of categories) {
    confusion[category][predicted] = 0;
  }
}

console.log(`\nEvaluating ${dataset.emails.length} sample emails...\n`);

for (const email of dataset.emails) {
  const result = classifyEmail(email);
  const expected = email.expectedKind;

  confusion[expected][result.kind]++;

  if (result.kind === expected) {
    correct++;
  } else {
    console.log(
      `MISCLASSIFIED ${email.id}: expected=${expected}, predicted=${result.kind}, subject="${email.subject}"`,
    );
  }
}

const accuracy = (correct / dataset.emails.length) * 100;

console.log("\n========== EVALUATION RESULTS ==========");
console.log(`Total emails: ${dataset.emails.length}`);
console.log(`Correct classifications: ${correct}`);
console.log(`Incorrect classifications: ${dataset.emails.length - correct}`);
console.log(`Classification accuracy: ${accuracy.toFixed(2)}%`);

console.log("\n========== ACCURACY BY CATEGORY ==========");

for (const category of categories) {
  const categoryEmails = dataset.emails.filter(
    (email) => email.expectedKind === category,
  );
  const categoryCorrect = confusion[category][category];
  const categoryAccuracy =
    categoryEmails.length === 0
      ? 0
      : (categoryCorrect / categoryEmails.length) * 100;

  console.log(
    `${category}: ${categoryCorrect}/${categoryEmails.length} correct (${categoryAccuracy.toFixed(2)}%)`,
  );
}

console.log("\n========== CONFUSION TABLE ==========");
console.log("Rows = expected category; columns = predicted category");
console.table(confusion);
