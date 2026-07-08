import assert from "node:assert/strict";
import test from "node:test";

import { summarizeTask } from "./index.js";

test("summarizeTask returns a safe compact summary", () => {
  assert.equal(
    summarizeTask({ title: "Review bridge flow", allowedFiles: ["README.md", "bridge/tools.py"] }),
    "Review bridge flow: 2 allowed files",
  );
});

test("summarizeTask handles missing fields", () => {
  assert.equal(summarizeTask({}), "untitled: 0 allowed files");
});
