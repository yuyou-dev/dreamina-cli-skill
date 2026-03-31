# Dreamina Wrapper Commands

## 1. Purpose

This reference describes the packaged Python wrapper scripts under `scripts/`. These wrappers are the preferred execution surface for the `dreamina-cli` skill.

They add:
- local path validation
- structured JSON success and failure payloads
- `--dry-run` support
- normalized argument names
- lightweight command-specific validation before invoking `dreamina`

When a flag combination is unclear, verify it with `dreamina <subcommand> -h`.

## 2. Discovery

Machine-readable inventory:

```bash
python3 .agent/skills/dreamina-cli/scripts/list_capabilities.py --format json
```

Readable inventory:

```bash
python3 .agent/skills/dreamina-cli/scripts/list_capabilities.py --format markdown
```

## 3. Wrapper catalog

### Image generation

- `text2image.py`
  - Required: `--prompt`
  - Optional: `--ratio`, `--resolution-type`, `--model-version`, `--poll`
- `image2image.py`
  - Required: `--images`
  - Optional: `--prompt`, `--ratio`, `--resolution-type`, `--model-version`, `--poll`
- `image_upscale.py`
  - Required: `--image`
  - Optional: `--resolution-type`, `--poll`

### Video generation

- `text2video.py`
  - Required: `--prompt`
  - Optional: `--duration`, `--ratio`, `--video-resolution`, `--model-version`, `--poll`
- `image2video.py`
  - Required: `--image`, `--prompt`
  - Optional: `--duration`, `--video-resolution`, `--model-version`, `--poll`
  - Notes:
    - model aliases `3.0_fast`, `3.0_pro`, `3.5_pro` are normalized to CLI canonical values
    - advanced controls require `--model-version`
- `frames2video.py`
  - Required: `--first`, `--last`, `--prompt`
  - Optional: `--duration`, `--video-resolution`, `--model-version`, `--poll`
- `multiframe2video.py`
  - Required: `--images`
  - Two-image mode:
    - use `--prompt`
    - optional `--duration`
  - Three-plus-image mode:
    - repeat `--transition-prompt`
    - optional repeated `--transition-duration`
  - Optional: `--poll`
- `multimodal2video.py`
  - Required: at least one `--image` or `--video`
  - Optional: repeated `--image`, repeated `--video`, repeated `--audio`, `--prompt`, `--duration`, `--ratio`, `--video-resolution`, `--model-version`, `--poll`

### Query, list, and account

- `query_result.py`
  - Required: `--submit-id`
  - Optional: `--download-dir`
- `list_task.py`
  - Optional: `--submit-id`, `--gen-status`, `--gen-task-type`, `--limit`, `--offset`
- `user_credit.py`
  - No task-specific parameters

### Session and environment

- `login.py`
  - Optional: `--debug`
- `logout.py`
  - No task-specific parameters
- `relogin.py`
  - Optional: `--debug`
- `version.py`
  - No task-specific parameters

## 4. Argument naming

The wrappers accept hyphen-style names and convert them to the CLI's required flag names.

Examples:
- `--model-version` becomes `--model_version`
- `--resolution-type` becomes `--resolution_type`
- `--video-resolution` becomes `--video_resolution`
- `--submit-id` becomes `--submit_id`

The underscore forms are also accepted when needed.

## 5. Common patterns

Inspect the generated CLI command without running it:

```bash
python3 .agent/skills/dreamina-cli/scripts/text2image.py \
  --prompt "clean silver ring product shot" \
  --ratio 1:1 \
  --resolution-type 2k \
  --dry-run
```

Submit a task and let Dreamina poll briefly:

```bash
python3 .agent/skills/dreamina-cli/scripts/text2video.py \
  --prompt "camera pushes toward a necklace on a gray stage" \
  --duration 5 \
  --poll 60
```

List successful tasks:

```bash
python3 .agent/skills/dreamina-cli/scripts/list_task.py --gen-status success --limit 20
```

## 6. Return contract

Success payload:

```json
{
  "ok": true,
  "command": "text2image",
  "cli_args": ["dreamina", "text2image", "..."],
  "data": {}
}
```

Failure payload:

```json
{
  "ok": false,
  "command": "text2image",
  "cli_args": ["dreamina", "text2image", "..."],
  "error": "normalized message",
  "details": ["detail 1", "detail 2"]
}
```

For generation wrappers:
- `ok: true` means the wrapper saw a valid async submit payload
- `submit_id` is available in `data.submit_id`
- `gen_status=fail` is converted into `ok: false`

## 7. Current validation scope

The wrappers currently validate:
- required fields
- file path existence
- known ratio/model/resolution choices
- command-specific range and combination rules
- multiframe transition counts
- multimodal input count limits

The wrappers do not currently inspect media duration or image dimensions. Dreamina CLI remains the final enforcer for those deeper server-side rules.
