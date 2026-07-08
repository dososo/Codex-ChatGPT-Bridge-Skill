export function summarizeTask(task) {
  const title = typeof task?.title === "string" && task.title.trim() ? task.title.trim() : "untitled";
  const allowedFiles = Array.isArray(task?.allowedFiles) ? task.allowedFiles.length : 0;
  return `${title}: ${allowedFiles} allowed files`;
}
