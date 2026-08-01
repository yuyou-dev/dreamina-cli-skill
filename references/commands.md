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
python3 ./scripts/list_capabilities.py --format json
```

Readable inventory:

```bash
python3 ./scripts/list_capabilities.py --format markdown
```

## 3. Wrapper catalog

### Image generation

- `text2image.py`
  - Required: `--prompt`, `--resolution-type`
  - Optional: `--session`, `--ratio`, paired `--width`/`--height`, `--model-version`, `--generate-num`, `--poll`
  - Supported `--model-version`: `3.0`, `3.1`, `4.0`, `4.1`, `4.5`, `4.6`, `4.7`, `5.0`, `5.0Pro`
  - Notes:
    - `5.0Pro` is the current CLI flag value for Seedream 5.0 Pro.
    - `5.0Pro` supports `--resolution-type 1k`, `2k`, or `4k`; default model is `5.0`.
    - `--generate-num` maps to CLI `--generate_num` and supports `1-10`.
- `image2image.py`
  - Required: `--images`, `--resolution-type`
  - Input count: `1-10`
  - Optional: `--prompt`, `--session`, `--ratio`, paired `--width`/`--height`, `--model-version`, `--generate-num`, `--poll`
  - Supported `--model-version`: `4.0`, `4.1`, `4.5`, `4.6`, `4.7`, `5.0`, `5.0Pro`
  - Notes:
    - `5.0Pro` is the current CLI flag value for Seedream 5.0 Pro.
    - `5.0Pro` supports `--resolution-type 1k`, `2k`, or `4k`; default model is `5.0`.
    - `--generate-num` maps to CLI `--generate_num` and supports `1-10`.
- `image_upscale.py`
  - Required: `--image`, `--resolution-type`
  - Optional: `--session`, `--poll`

Custom image dimensions require paired `--width` and `--height` and cannot be combined with `--ratio`. Limits are 512-2016 per side and 1,763,584 total pixels at 1k; 768-3072 and 4,194,304 at 2k; 1536-6240 and 16,777,216 at 4k. Text-to-image models 3.0/3.1 support custom dimensions only at 2k.

### Video generation

- `text2video.py`
  - Required: `--prompt`, `--video-resolution`
  - Optional: `--session`, `--duration`, `--ratio`, `--model-version`, `--poll`
  - Notes:
    - supported `--model-version`: `seedance2.0`, `seedance2.0fast`, `seedance2.0_vip`, `seedance2.0fast_vip`, `seedance2.0mini`, `seedance2.5`
    - `--video-resolution 1080p` or `4k` requires `--model-version seedance2.0_vip`

Video model matrix:

- Seedance 2.5: 4-30 seconds, 480p/720p, VIP-only
- Seedance 2.0 VIP: 4-15 seconds, 720p/1080p/4k
- Other Seedance 2.0 variants: 4-15 seconds, 720p
- Image-to-video Seedance 1.0 Fast: 5-10 seconds, 720p
- Seedance 1.5 Pro: 5-12 seconds, 720p
- `image2video.py`
  - Required: `--image`, `--prompt`, `--video-resolution`
  - Optional: `--session`, `--duration`, `--model-version`, `--poll`
  - Notes:
    - supported `--model-version`: `seedance1.0fast`, `seedance1.5pro`, `seedance2.0`, `seedance2.0fast`, `seedance2.0_vip`, `seedance2.0fast_vip`, `seedance2.0mini`, `seedance2.5`
    - retired 3.x model aliases are rejected
    - `--video-resolution 1080p` or `4k` requires `--model-version seedance2.0_vip`
- `frames2video.py`
  - Required: `--first`, `--last`, `--prompt`, `--video-resolution`
  - Optional: `--session`, `--duration`, `--model-version`, `--poll`
  - Notes:
    - supported `--model-version`: `seedance1.5pro`, `seedance2.0`, `seedance2.0fast`, `seedance2.0_vip`, `seedance2.0fast_vip`, `seedance2.0mini`, `seedance2.5`
    - `--video-resolution 1080p` or `4k` requires `--model-version seedance2.0_vip`
- `multiframe2video.py`
  - Required: `--images`, `--video-resolution` (`720p` or `1080p`)
  - Two-image mode:
    - use `--prompt`
    - optional `--duration`
  - Three-plus-image mode:
    - repeat `--transition-prompt`
    - optional repeated `--transition-duration`
  - Optional: `--session`, `--poll`
- `multimodal2video.py`
  - Required: `--video-resolution`; Seedance 2.0 also requires an image or video, while Seedance 2.5 accepts audio-only input
  - Optional: repeated `--image`, repeated `--video`, repeated `--audio`, `--prompt`, `--session`, `--duration`, `--ratio`, `--model-version`, `--poll`
  - Notes:
    - supported `--model-version`: `seedance2.0`, `seedance2.0fast`, `seedance2.0_vip`, `seedance2.0fast_vip`, `seedance2.0mini`, `seedance2.5`
    - default model is `seedance2.0_vip`
    - Seedance 2.5 supports 30 images, 10 videos, 10 audio files, 50 total inputs, and 2-30 second reference media
    - `--video-resolution 1080p` or `4k` requires `--model-version seedance2.0_vip`

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
  - Optional: `--headless`
- `login_checklogin.py`
  - Required: `--device-code`
  - Optional: `--poll`
- `logout.py`
  - No task-specific parameters
- `relogin.py`
  - Optional: `--headless`
- `session.py`
  - Required: `--action`
  - Actions:
    - `create`: optional `--name`
    - `list`: optional `--max-count`
    - `search`: required `--name`
    - `rename`: required `--session-id`, `--name`
    - `delete`: required `--session-id`
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
python3 ./scripts/text2image.py \
  --prompt "clean silver ring product shot" \
  --ratio 1:1 \
  --resolution-type 2k \
  --dry-run
```

Submit a task and let Dreamina poll briefly:

```bash
python3 ./scripts/text2video.py \
  --prompt "camera pushes toward a necklace on a gray stage" \
  --duration 5 \
  --poll 60
```

List successful tasks:

```bash
python3 ./scripts/list_task.py --gen-status success --limit 20
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

The wrappers enforce custom image dimension bounds but do not inspect reference media duration. Dreamina CLI remains the final enforcer for backend-specific rules.
