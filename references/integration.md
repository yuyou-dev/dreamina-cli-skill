# Dreamina Skill Integration

## 1. Vibe Coding IDE

This skill is designed to run directly from the repository workspace.

Recommended agent pattern:
1. Use `list_capabilities.py` when the task is broad or exploratory.
2. Pick one wrapper script.
3. Use `--dry-run` for confirmation when the user request is ambiguous, expensive, or high risk.
4. Run the real wrapper script.
5. Read the JSON payload and continue with `submit_id` when needed.

Minimal example:

```bash
python3 .agent/skills/dreamina-cli/scripts/list_capabilities.py --format json
python3 .agent/skills/dreamina-cli/scripts/text2image.py --prompt "luxury ring on white" --ratio 1:1 --dry-run
python3 .agent/skills/dreamina-cli/scripts/text2image.py --prompt "luxury ring on white" --ratio 1:1 --poll 60
```

## 2. Portability strategy

The skill is intentionally split into:
- `SKILL.md`
  - trigger rules and operating procedure
- `scripts/`
  - deterministic execution layer
- `references/`
  - detailed command and integration guidance

That structure makes it easier to move into other agent runtimes.

## 3. OpenClaw-style runtimes

Recommended adaptation pattern:
- mount or copy the `dreamina-cli` skill folder into the runtime's skill registry
- preserve relative paths inside the skill
- expose `python3` and `dreamina` in the runtime environment
- use `list_capabilities.py --format json` as the discovery layer
- treat wrapper JSON as the tool response contract

Suggested execution policy:
- discovery step: `list_capabilities.py`
- planning step: run target wrapper with `--dry-run`
- execution step: run target wrapper without `--dry-run`
- follow-up step: use `query_result.py` with `submit_id`

## 4. DeerFlow-style runtimes

Recommended adaptation pattern:
- register each wrapper script as a skill action or tool node
- keep the command name aligned with the script filename
- pass user parameters directly to the wrapper
- parse `ok`, `data`, `error`, and `details`

Suggested node mapping:
- generation nodes:
  - `text2image`
  - `image2image`
  - `image_upscale`
  - `text2video`
  - `image2video`
  - `frames2video`
  - `multiframe2video`
  - `multimodal2video`
- utility nodes:
  - `query_result`
  - `list_task`
  - `user_credit`
  - `login`
  - `logout`
  - `relogin`
  - `version`
  - `list_capabilities`

## 5. Integration rules

- Prefer wrapper scripts over raw CLI calls for supported commands.
- Preserve the wrapper JSON contract; do not strip `cli_args`, because it is useful for audit and debugging.
- Reuse `submit_id` across nodes instead of re-submitting the same generation request.
- If the wrapper returns `AigcComplianceConfirmationRequired`, surface that to the user instead of retry-looping.
- Keep Dreamina login state outside the skill logic; the skill should operate on the currently active local session.
