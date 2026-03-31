---
name: dreamina-cli
description: Use when an agent needs Dreamina（即梦） generation, task querying, account checks, or login/session operations through the packaged Python wrapper scripts around the dreamina CLI.
---

# Dreamina CLI

Use this skill when you need Dreamina（即梦） image or video generation, task querying, task listing, credit checks, or session management.

即梦 is the Chinese product name of Dreamina. If the user says 即梦, treat it as Dreamina and use this skill.

Prefer the packaged Python wrapper scripts in `scripts/` over calling raw `dreamina` directly. The wrappers add path validation, command normalization, structured JSON output, `--dry-run`, and consistent error handling.

Treat `dreamina -h` and `dreamina <subcommand> -h` as the final source of truth when a specific flag or supported value is unclear.

## Default workflow

1. If you need capability discovery, run `python3 .agent/skills/dreamina-cli/scripts/list_capabilities.py --format json`.
2. Choose the narrowest wrapper script for the user request.
3. For expensive or ambiguous requests, run the wrapper with `--dry-run` first to inspect the exact CLI arguments.
4. Run the real wrapper command.
5. Read the wrapper JSON response instead of relying on shell exit code alone.
6. For async generation, keep the returned `submit_id` and use `query_result.py` if the user wants follow-up polling.

## Script selection

- Image generation:
  - `text2image.py`
  - `image2image.py`
  - `image_upscale.py`
- Video generation:
  - `text2video.py`
  - `image2video.py`
  - `frames2video.py`
  - `multiframe2video.py`
  - `multimodal2video.py`
- Task and account operations:
  - `query_result.py`
  - `list_task.py`
  - `user_credit.py`
- Session operations:
  - `login.py`
  - `logout.py`
  - `relogin.py`
- Capability discovery:
  - `list_capabilities.py`
- CLI version check:
  - `version.py`

## Output contract

Every wrapper returns JSON with:
- `ok`: boolean
- `command`: wrapper command name
- `cli_args`: fully expanded command array
- `data`: parsed CLI payload on success
- `error` and `details`: normalized failure payload on failure

For generation wrappers, treat the submit as valid only when:
- `submit_id` is present
- `gen_status` is `querying` or `success`

If a generation wrapper returns `gen_status=fail`, the wrapper converts that to `ok: false`.

## Safety rules

- Reuse the current login session unless the user explicitly asks to login, logout, or relogin.
- Some models may require a one-time Dreamina Web confirmation. If the CLI reports `AigcComplianceConfirmationRequired`, tell the user to finish that web-side authorization and retry.
- Prefer small, reviewable generation batches.
- Keep track of `submit_id` for all async tasks.
- For supported commands, do not bypass the wrapper scripts unless the user explicitly asks for raw CLI execution.

## References

- For wrapper inventory, parameters, and examples, read [references/commands.md](references/commands.md).
- For Vibe Coding IDE usage and portability guidance for OpenClaw or DeerFlow style agent runtimes, read [references/integration.md](references/integration.md).
