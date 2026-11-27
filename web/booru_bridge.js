// Adds "Use in Booru Prompt Gallery" to ComfyUI's File menu and to the top action bar.
// The workflow actions menu (workflow name, top left) is built inside the frontend and has no extension hook.
// The graph is converted with ComfyUI's own app.graphToPrompt(); never convert by hand.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const COMMAND_ID = "BooruPromptGallery.Publish";

function notify(severity, summary, detail) {
  const toast = app.extensionManager?.toast;
  if (toast?.add) {
    toast.add({ severity, summary, detail, life: severity === "success" ? 4000 : 8000 });
  } else {
    alert(detail ? `${summary}\n${detail}` : summary);
  }
}

// graphToPrompt() keeps every node, not only those that lead to an output, so ask the
// server which classes are output nodes. If a lookup fails, do not block publishing.
async function hasOutputNode(prompt) {
  const classes = [...new Set(Object.values(prompt).map((n) => n.class_type))];
  const flags = await Promise.all(
    classes.map(async (cls) => {
      try {
        const res = await api.fetchApi(`/object_info/${encodeURIComponent(cls)}`);
        if (!res.ok) return true;
        return Boolean((await res.json())?.[cls]?.output_node);
      } catch {
        return true;
      }
    })
  );
  return flags.some(Boolean);
}

function workflowName() {
  // Active tab's file name; unsaved workflows still have a temporary name.
  const filename = app.extensionManager?.workflow?.activeWorkflow?.filename;
  const name = String(filename ?? "").replace(/\.json$/i, "").trim().slice(0, 120);
  return name || "Untitled workflow";
}

async function publish() {
  try {
    const { workflow, output } = await app.graphToPrompt();
    if (!output || Object.keys(output).length === 0 || !(await hasOutputNode(output))) {
      notify("error", "This workflow has no output node", "Add a node that saves or previews an image, then try again.");
      return;
    }
    const name = workflowName();
    const res = await api.fetchApi("/booru_bridge/workflows", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, ui: workflow, api: output }),
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        if (body?.error) detail = String(body.error);
      } catch {
        // Not JSON: keep the status.
      }
      notify("error", "Could not publish the workflow", detail);
      return;
    }
    notify("success", "Ready in Booru Prompt Gallery", `"${name}" can now be picked in the gallery's ComfyUI panel.`);
  } catch (err) {
    notify("error", "Could not publish the workflow", err?.message ?? String(err));
  }
}

app.registerExtension({
  name: "BooruPromptGallery.Bridge",
  commands: [{ id: COMMAND_ID, label: "Use in Booru Prompt Gallery", icon: "pi pi-send", function: publish }],
  menuCommands: [{ path: ["File"], commands: [COMMAND_ID] }],
  actionBarButtons: [
    { icon: "pi pi-send", label: "Use in Booru Prompt Gallery", tooltip: "Use this workflow in Booru Prompt Gallery", onClick: publish },
  ],
});
