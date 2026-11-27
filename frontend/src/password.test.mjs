import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const source = await readFile(new URL("./password.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { PASSWORD_MIN_LENGTH, passwordPolicyError } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);

test("accepts passwords that meet every requirement", () => {
  assert.equal(passwordPolicyError("Abcdefg1!"), null);
  assert.equal(passwordPolicyError("LongerPassword9#"), null);
});

test("rejects passwords below the minimum length", () => {
  assert.equal(
    passwordPolicyError("Aa1!"),
    `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`
  );
});

test("reports the missing character class", () => {
  assert.equal(passwordPolicyError("lowercase1!"), "Password must include an uppercase letter.");
  assert.equal(passwordPolicyError("UPPERCASE1!"), "Password must include a lowercase letter.");
  assert.equal(passwordPolicyError("NoNumbers!!"), "Password must include a number.");
  assert.equal(passwordPolicyError("NoSpecial11"), "Password must include a special character.");
  assert.equal(passwordPolicyError("Has Space 1A"), "Password must include a special character.");
});
