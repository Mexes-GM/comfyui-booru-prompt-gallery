# Booru Prompt Gallery for ComfyUI

A node pack for the [Booru Prompt Gallery](https://booru-prompt-gallery.vercel.app) website. It has no nodes yet. Its first feature lets the gallery's Send buttons queue prompts in your local ComfyUI.

ComfyUI normally rejects requests that come from another website. This pack keeps that rule except for a short list of exact origins. A request from a listed origin is let through; a request from any other origin still goes to ComfyUI's own check and gets a 403.

## Why not `--enable-cors-header`

That flag lets any website queue jobs on your ComfyUI, because a plain `text/plain` POST needs no preflight.

## Install

### ComfyUI Manager

1. In ComfyUI, open Manager, then Custom Nodes Manager.
2. Search for "Booru Prompt Gallery" and click Install.
3. Restart ComfyUI.

The pack is listed in the [ComfyUI registry](https://registry.comfy.org/nodes/comfyui-booru-prompt-gallery).

### comfy-cli

```
comfy node install comfyui-booru-prompt-gallery
```

Then restart ComfyUI.

### Manual

1. Clone this repository into `ComfyUI/custom_nodes`:

   ```
   cd ComfyUI/custom_nodes
   git clone https://github.com/Mexes-GM/comfyui-booru-prompt-gallery
   ```

2. Restart ComfyUI.

After a restart, the startup log shows `Booru Prompt Gallery bridge installed` followed by the allowed origins. Log lines from this pack use the logger name `booru_prompt_gallery`.

If ComfyUI is started with `--enable-cors-header`, or a later ComfyUI version changes its server code, the pack cannot find the check it replaces. It logs a warning and stays inactive.

## Use a workflow in the gallery

1. Open the workflow in ComfyUI.
2. Click Use in Booru Prompt Gallery in the top bar, next to Run. You can also open the ComfyUI menu (the logo at the top left) and choose File, then Use in Booru Prompt Gallery.

ComfyUI shows a message when the workflow is ready. It appears in the gallery's ComfyUI panel under the name of the workflow tab. Publishing again with the same name replaces the earlier copy. The workflow needs at least one output node, such as Save Image or Preview Image.

## Allowed origins

Built in:

- `https://booru-prompt-gallery.vercel.app`
- `https://booru-prompt-gallery.netlify.app`
- `http://localhost:3000`

To add more, create `booru_bridge.json` in the `default` folder of the ComfyUI user directory (by default `ComfyUI/user/default/booru_bridge.json`) and restart ComfyUI:

```json
{ "extra_origins": ["https://my-gallery.example"] }
```

Each entry must be exactly `scheme://host` or `scheme://host:port`, with `http` or `https`. Paths, trailing slashes, wildcards, `*` and `null` are rejected and logged. Matching is exact, apart from lowercasing the scheme and host.

## HTTP API

Every route is also available under `/api/booru_bridge/...`.

| Route | Description |
| --- | --- |
| `GET /booru_bridge/info` | `{"version", "origins", "middleware"}`. `middleware` is `ok`, `already` or `missing`. |
| `GET /booru_bridge/workflows` | `{"workflows": [{"id", "name", "updated"}]}`, newest first. |
| `GET /booru_bridge/workflows/{id}` | `{"id", "name", "updated", "ui", "api"}`, or 404. |
| `POST /booru_bridge/workflows` | Body `{"name", "ui", "api"}`. Saves a workflow; a workflow with the same name is overwritten. Returns `{"id", "name", "updated"}`. |

`api` is a ComfyUI API-format prompt: a non-empty object whose values each have a `class_type`. `ui` is the editor graph, or `null`. `name` is 1 to 120 characters. Bodies over 20 MB are rejected. Errors are JSON: `{"error": "..."}`.

The allowed web origins can read workflows but cannot save them. A POST whose `Origin` header differs from the ComfyUI host gets a 403, so only ComfyUI's own page and clients that send no `Origin` header (scripts, curl) can save.

Workflows are stored as `<user dir>/default/booru_bridge/workflows/<id>.json`.

## Adding nodes

Put one file per node in `nodes/`, with its own `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`. The pack imports every file in that folder and merges the mappings. A file that fails to import is logged and skipped.

## Development and testing

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt     # Windows; use .venv/bin/python elsewhere
.venv/Scripts/python -m pytest -m "not integration"
```

The integration tests start their own ComfyUI on port 8191, on the CPU, with only this pack loaded and temporary user, input and output folders. They need a ComfyUI checkout, given in `COMFYUI_PATH`, and are skipped when it is not set:

```
COMFYUI_PATH=/path/to/ComfyUI .venv/Scripts/python -m pytest -m integration
```

ComfyUI is started with `COMFYUI_PYTHON` if set, otherwise with the `.venv` inside the ComfyUI folder, otherwise with the Python running pytest. This repository's folder must be named `comfyui-booru-prompt-gallery`, because the test loads it by that name. The tests fail if port 8191 is already in use.

## Uninstall

Delete the `comfyui-booru-prompt-gallery` folder from `custom_nodes` and restart ComfyUI. Saved workflows stay in `user/default/booru_bridge/`; delete that folder and `user/default/booru_bridge.json` if you no longer want them.

## Licence

GPL-3.0. See `LICENSE`.
