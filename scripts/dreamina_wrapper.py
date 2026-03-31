#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


GENERATION_COMMANDS = {
    "text2image",
    "image2image",
    "image_upscale",
    "text2video",
    "image2video",
    "frames2video",
    "multiframe2video",
    "multimodal2video",
}

VALID_SUBMIT_STATUSES = {"querying", "success"}
IMAGE2VIDEO_MODEL_ALIASES = {
    "3.0_fast": "3.0fast",
    "3.0_pro": "3.0pro",
    "3.5_pro": "3.5pro",
}


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    cli_flag: str
    help: str
    value_type: str = "str"
    required: bool = False
    multiple: bool = False
    choices: tuple[str, ...] = ()
    csv_split: bool = False
    min_value: float | int | None = None
    max_value: float | int | None = None
    path_mode: str | None = None
    create_dir: bool = False

    @property
    def argument_names(self) -> tuple[str, ...]:
        names = []
        hyphen_name = f"--{self.key.replace('_', '-')}"
        underscore_name = f"--{self.key}"

        for candidate in (hyphen_name, underscore_name):
            if candidate not in names:
                names.append(candidate)

        cli_name = f"--{self.cli_flag}"
        if cli_name not in names:
            names.append(cli_name)

        return tuple(names)


@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str
    output_mode: str
    parameters: tuple[ParameterSpec, ...] = field(default_factory=tuple)
    examples: tuple[str, ...] = field(default_factory=tuple)
    validator: Callable[[argparse.Namespace], None] | None = None


class DreaminaWrapperError(Exception):
    def __init__(
        self,
        message: str,
        details: Sequence[str] | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = [line for line in (details or []) if line]
        self.exit_code = exit_code


def compact_lines(text: str) -> list[str]:
    return [line.strip() for line in strip_ansi(text).splitlines() if line.strip()]


def strip_ansi(text: str) -> str:
    import re

    return re.sub(r"\u001B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)


def extract_json_text(text: str) -> str | None:
    trimmed = text.strip()
    object_start = trimmed.find("{")
    array_start = trimmed.find("[")

    if object_start < 0 and array_start < 0:
        return None

    if object_start >= 0 and array_start >= 0:
        start = min(object_start, array_start)
    else:
        start = max(object_start, array_start)

    candidate = trimmed[start:]
    object_end = candidate.rfind("}")
    array_end = candidate.rfind("]")
    end = max(object_end, array_end)

    if end < 0:
        return None

    return candidate[: end + 1]


def parse_json_payload(stdout: str, stderr: str = "") -> Any:
    stdout_json = extract_json_text(stdout)
    if stdout_json:
        return json.loads(stdout_json)

    combined_json = extract_json_text(f"{stdout}\n{stderr}")
    if combined_json:
        return json.loads(combined_json)

    raise DreaminaWrapperError(
        "Dreamina CLI did not return parseable JSON.",
        details=[*compact_lines(stdout), *compact_lines(stderr)],
    )


def last_meaningful_line(stdout: str, stderr: str, fallback: str) -> str:
    stderr_lines = compact_lines(stderr)
    stdout_lines = compact_lines(stdout)
    line = stderr_lines[-1] if stderr_lines else (stdout_lines[-1] if stdout_lines else fallback)

    if "AigcComplianceConfirmationRequired" in line:
        return "This model requires a one-time Dreamina Web authorization confirmation before retrying."

    if "record not found" in line or "not found" in line:
        return "The Dreamina task could not be found. Check whether submit_id is correct."

    return line


def normalize_exec_error(
    command: list[str],
    returncode: int,
    stdout: str,
    stderr: str,
) -> DreaminaWrapperError:
    fallback = f"Dreamina CLI failed with exit code {returncode}."
    return DreaminaWrapperError(
        last_meaningful_line(stdout, stderr, fallback),
        details=[*compact_lines(stderr), *compact_lines(stdout), f"command: {' '.join(command)}"],
        exit_code=returncode or 1,
    )


def json_dump(payload: Any, exit_code: int = 0) -> int:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return exit_code


def split_csv_values(raw_values: Iterable[str]) -> list[str]:
    values: list[str] = []
    for raw_value in raw_values:
        for item in raw_value.split(","):
            normalized = item.strip()
            if normalized:
                values.append(normalized)
    return values


def validate_path(raw_value: str, *, path_mode: str, create_dir: bool = False) -> str:
    path = Path(raw_value).expanduser()

    if create_dir:
        path.mkdir(parents=True, exist_ok=True)
        return str(path.resolve())

    if not path.exists():
        raise DreaminaWrapperError(f"Local path does not exist: {raw_value}")

    if path_mode == "file" and not path.is_file():
        raise DreaminaWrapperError(f"Expected a file path: {raw_value}")

    if path_mode == "dir" and not path.is_dir():
        raise DreaminaWrapperError(f"Expected a directory path: {raw_value}")

    return str(path.resolve())


def normalize_namespace(spec: CommandSpec, namespace: argparse.Namespace) -> argparse.Namespace:
    for parameter in spec.parameters:
        value = getattr(namespace, parameter.key)

        if parameter.value_type == "bool":
            continue

        if value is None:
            continue

        if parameter.multiple:
            raw_values = value or []

            if parameter.csv_split:
                values = split_csv_values(raw_values)
            elif parameter.value_type == "str":
                values = [item.strip() for item in raw_values if item and item.strip()]
            else:
                values = [item for item in raw_values if item is not None]

            if parameter.path_mode:
                values = [
                    validate_path(
                        item,
                        path_mode=parameter.path_mode,
                        create_dir=parameter.create_dir,
                    )
                    for item in values
                ]

            setattr(namespace, parameter.key, values)
            continue

        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                setattr(namespace, parameter.key, None)
                continue

            if parameter.path_mode:
                normalized = validate_path(
                    normalized,
                    path_mode=parameter.path_mode,
                    create_dir=parameter.create_dir,
                )

            setattr(namespace, parameter.key, normalized)

    return namespace


def validate_parameter_ranges(spec: CommandSpec, namespace: argparse.Namespace) -> None:
    for parameter in spec.parameters:
        value = getattr(namespace, parameter.key)

        if value is None or value is False:
            if parameter.required:
                raise DreaminaWrapperError(f"Missing required parameter: --{parameter.key.replace('_', '-')}")
            continue

        values = value if parameter.multiple else [value]

        if parameter.required and parameter.multiple and len(values) == 0:
            raise DreaminaWrapperError(f"Missing required parameter: --{parameter.key.replace('_', '-')}")

        for item in values:
            if parameter.choices and item not in parameter.choices:
                allowed = ", ".join(parameter.choices)
                raise DreaminaWrapperError(
                    f"Unsupported value for --{parameter.key.replace('_', '-')}: {item}",
                    details=[f"allowed values: {allowed}"],
                )

            if parameter.min_value is not None and item < parameter.min_value:
                raise DreaminaWrapperError(
                    f"--{parameter.key.replace('_', '-')} must be >= {parameter.min_value}."
                )

            if parameter.max_value is not None and item > parameter.max_value:
                raise DreaminaWrapperError(
                    f"--{parameter.key.replace('_', '-')} must be <= {parameter.max_value}."
                )


def validate_text2image(namespace: argparse.Namespace) -> None:
    if namespace.resolution_type == "1k" and namespace.model_version not in {"3.0", "3.1"}:
        raise DreaminaWrapperError("resolution_type=1k requires model_version=3.0 or 3.1.")

    if namespace.resolution_type == "4k" and namespace.model_version and namespace.model_version not in {
        "4.0",
        "4.1",
        "4.5",
        "4.6",
        "5.0",
        "lab",
    }:
        raise DreaminaWrapperError("resolution_type=4k only supports 4.x, 5.0, or lab.")


def validate_image2video(namespace: argparse.Namespace) -> None:
    if namespace.model_version:
        namespace.model_version = IMAGE2VIDEO_MODEL_ALIASES.get(namespace.model_version, namespace.model_version)

    if namespace.model_version and namespace.model_version not in {
        "3.0",
        "3.0fast",
        "3.0pro",
        "3.5pro",
        "seedance2.0",
        "seedance2.0fast",
    }:
        raise DreaminaWrapperError(
            f"Unsupported image2video model_version: {namespace.model_version}"
        )

    advanced_control_requested = any(
        value is not None
        for value in (namespace.duration, namespace.video_resolution, namespace.model_version)
    )
    if advanced_control_requested and not namespace.model_version:
        raise DreaminaWrapperError(
            "When using duration or video_resolution, model_version must also be provided."
        )

    if not namespace.model_version:
        return

    if namespace.model_version in {"3.0", "3.0fast"}:
        validate_integer_in_range(namespace.duration, 3, 10, "duration")
        validate_choice(namespace.video_resolution, {"720p", "1080p"}, "video_resolution")
        return

    if namespace.model_version == "3.0pro":
        validate_integer_in_range(namespace.duration, 3, 10, "duration")
        validate_choice(namespace.video_resolution, {"1080p"}, "video_resolution")
        return

    if namespace.model_version == "3.5pro":
        validate_integer_in_range(namespace.duration, 4, 12, "duration")
        validate_choice(namespace.video_resolution, {"720p", "1080p"}, "video_resolution")
        return

    validate_integer_in_range(namespace.duration, 4, 15, "duration")
    validate_choice(namespace.video_resolution, {"720p"}, "video_resolution")


def validate_frames2video(namespace: argparse.Namespace) -> None:
    effective_model = namespace.model_version or "seedance2.0fast"
    namespace.effective_model_version = effective_model

    if effective_model == "3.0":
        validate_integer_in_range(namespace.duration, 3, 10, "duration")
        validate_choice(namespace.video_resolution, {"720p", "1080p"}, "video_resolution")
        return

    if effective_model == "3.5pro":
        validate_integer_in_range(namespace.duration, 4, 12, "duration")
        validate_choice(namespace.video_resolution, {"720p", "1080p"}, "video_resolution")
        return

    validate_integer_in_range(namespace.duration, 4, 15, "duration")
    validate_choice(namespace.video_resolution, {"720p"}, "video_resolution")


def validate_multiframe2video(namespace: argparse.Namespace) -> None:
    image_count = len(namespace.images or [])
    if image_count < 2 or image_count > 20:
        raise DreaminaWrapperError("multiframe2video requires 2 to 20 images.")

    transition_count = image_count - 1
    transition_prompts = namespace.transition_prompt or []
    transition_durations = namespace.transition_duration or []

    if image_count == 2:
        if not namespace.prompt:
            raise DreaminaWrapperError("Exactly 2 images require --prompt.")
        if transition_prompts or transition_durations:
            raise DreaminaWrapperError(
                "For exactly 2 images, use --prompt and optional --duration instead of transition flags."
            )
        validate_float_in_range(namespace.duration, 0.5, 8, "duration")
        if namespace.duration is not None and namespace.duration < 2:
            raise DreaminaWrapperError("For exactly 2 images, duration must be at least 2 seconds.")
        return

    if namespace.prompt is not None or namespace.duration is not None:
        raise DreaminaWrapperError(
            "For 3 or more images, use transition_prompt and transition_duration instead of prompt/duration."
        )

    if len(transition_prompts) != transition_count:
        raise DreaminaWrapperError(
            f"{image_count} images require {transition_count} transition_prompt values."
        )

    if any(not prompt.strip() for prompt in transition_prompts):
        raise DreaminaWrapperError("Each transition_prompt must be non-empty.")

    if transition_durations and len(transition_durations) != transition_count:
        raise DreaminaWrapperError(
            f"{image_count} images require either 0 or {transition_count} transition_duration values."
        )

    effective_durations = transition_durations or [3.0] * transition_count
    for value in effective_durations:
        if value < 0.5 or value > 8:
            raise DreaminaWrapperError("Each transition_duration must be between 0.5 and 8 seconds.")

    if sum(effective_durations) < 2:
        raise DreaminaWrapperError("The total multiframe2video duration must be at least 2 seconds.")


def validate_multimodal2video(namespace: argparse.Namespace) -> None:
    images = namespace.image or []
    videos = namespace.video or []
    audios = namespace.audio or []

    if len(images) > 9:
        raise DreaminaWrapperError("multimodal2video supports at most 9 images.")

    if len(videos) > 3:
        raise DreaminaWrapperError("multimodal2video supports at most 3 videos.")

    if len(audios) > 3:
        raise DreaminaWrapperError("multimodal2video supports at most 3 audio files.")

    if not images and not videos:
        raise DreaminaWrapperError("multimodal2video requires at least one image or one video.")


def validate_integer_in_range(
    value: int | None,
    minimum: int,
    maximum: int,
    name: str,
) -> None:
    if value is None:
        return

    if value < minimum or value > maximum:
        raise DreaminaWrapperError(f"{name} must be between {minimum} and {maximum}.")


def validate_float_in_range(
    value: float | None,
    minimum: float,
    maximum: float,
    name: str,
) -> None:
    if value is None:
        return

    if value < minimum or value > maximum:
        raise DreaminaWrapperError(f"{name} must be between {minimum} and {maximum}.")


def validate_choice(value: str | None, allowed: set[str], name: str) -> None:
    if value is None:
        return

    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise DreaminaWrapperError(f"{name} must be one of: {allowed_text}.")


COMMAND_SPECS: dict[str, CommandSpec] = {
    "text2image": CommandSpec(
        name="text2image",
        description="Submit a Dreamina text-to-image task with normalized arguments and JSON output.",
        output_mode="json",
        validator=validate_text2image,
        parameters=(
            ParameterSpec("prompt", "prompt", "Generation prompt.", required=True),
            ParameterSpec(
                "ratio",
                "ratio",
                "Output aspect ratio.",
                choices=("21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"),
            ),
            ParameterSpec(
                "resolution_type",
                "resolution_type",
                "Resolution tier.",
                choices=("1k", "2k", "4k"),
            ),
            ParameterSpec(
                "model_version",
                "model_version",
                "Model version.",
                choices=("3.0", "3.1", "4.0", "4.1", "4.5", "4.6", "5.0", "lab"),
            ),
            ParameterSpec("poll", "poll", "Optional polling window in seconds.", value_type="int", min_value=0),
        ),
        examples=(
            'python3 .agent/skills/dreamina-cli/scripts/text2image.py --prompt "a silver ring on white" --ratio 1:1 --resolution-type 2k',
        ),
    ),
    "image2image": CommandSpec(
        name="image2image",
        description="Submit a Dreamina image-to-image task.",
        output_mode="json",
        parameters=(
            ParameterSpec("images", "images", "One or more local image paths.", required=True, multiple=True, csv_split=True, path_mode="file"),
            ParameterSpec("prompt", "prompt", "Edit prompt."),
            ParameterSpec(
                "ratio",
                "ratio",
                "Output aspect ratio.",
                choices=("21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"),
            ),
            ParameterSpec(
                "resolution_type",
                "resolution_type",
                "Resolution tier.",
                choices=("2k", "4k"),
            ),
            ParameterSpec(
                "model_version",
                "model_version",
                "Model version.",
                choices=("4.0", "4.1", "4.5", "4.6", "5.0", "lab"),
            ),
            ParameterSpec("poll", "poll", "Optional polling window in seconds.", value_type="int", min_value=0),
        ),
        examples=(
            'python3 .agent/skills/dreamina-cli/scripts/image2image.py --images ./ref-1.png --images ./ref-2.png --prompt "white background commercial product shot"',
        ),
    ),
    "image_upscale": CommandSpec(
        name="image_upscale",
        description="Submit a Dreamina image upscale task.",
        output_mode="json",
        parameters=(
            ParameterSpec("image", "image", "Local image path.", required=True, path_mode="file"),
            ParameterSpec(
                "resolution_type",
                "resolution_type",
                "Target resolution.",
                choices=("2k", "4k", "8k"),
            ),
            ParameterSpec("poll", "poll", "Optional polling window in seconds.", value_type="int", min_value=0),
        ),
        examples=(
            "python3 .agent/skills/dreamina-cli/scripts/image_upscale.py --image ./product.png --resolution-type 4k",
        ),
    ),
    "text2video": CommandSpec(
        name="text2video",
        description="Submit a Dreamina text-to-video task.",
        output_mode="json",
        parameters=(
            ParameterSpec("prompt", "prompt", "Generation prompt.", required=True),
            ParameterSpec("duration", "duration", "Video duration in seconds.", value_type="int", min_value=4, max_value=15),
            ParameterSpec(
                "ratio",
                "ratio",
                "Output aspect ratio.",
                choices=("1:1", "3:4", "16:9", "4:3", "9:16", "21:9"),
            ),
            ParameterSpec(
                "video_resolution",
                "video_resolution",
                "Video resolution.",
                choices=("720p",),
            ),
            ParameterSpec(
                "model_version",
                "model_version",
                "Model version.",
                choices=("seedance2.0", "seedance2.0fast"),
            ),
            ParameterSpec("poll", "poll", "Optional polling window in seconds.", value_type="int", min_value=0),
        ),
        examples=(
            'python3 .agent/skills/dreamina-cli/scripts/text2video.py --prompt "camera slowly pushes toward a diamond necklace" --duration 5',
        ),
    ),
    "image2video": CommandSpec(
        name="image2video",
        description="Submit a Dreamina image-to-video task.",
        output_mode="json",
        validator=validate_image2video,
        parameters=(
            ParameterSpec("image", "image", "Local first-frame image path.", required=True, path_mode="file"),
            ParameterSpec("prompt", "prompt", "Generation prompt.", required=True),
            ParameterSpec("duration", "duration", "Advanced duration override.", value_type="int"),
            ParameterSpec("video_resolution", "video_resolution", "Advanced resolution override."),
            ParameterSpec("model_version", "model_version", "Advanced model override."),
            ParameterSpec("poll", "poll", "Optional polling window in seconds.", value_type="int", min_value=0),
        ),
        examples=(
            'python3 .agent/skills/dreamina-cli/scripts/image2video.py --image ./cover.png --prompt "subtle camera push in" --model-version 3.5pro --duration 6 --video-resolution 1080p',
        ),
    ),
    "frames2video": CommandSpec(
        name="frames2video",
        description="Submit a Dreamina first-last-frames video task.",
        output_mode="json",
        validator=validate_frames2video,
        parameters=(
            ParameterSpec("first", "first", "Local first-frame image path.", required=True, path_mode="file"),
            ParameterSpec("last", "last", "Local last-frame image path.", required=True, path_mode="file"),
            ParameterSpec("prompt", "prompt", "Generation prompt.", required=True),
            ParameterSpec(
                "model_version",
                "model_version",
                "Model version.",
                choices=("3.0", "3.5pro", "seedance2.0", "seedance2.0fast"),
            ),
            ParameterSpec("duration", "duration", "Video duration in seconds.", value_type="int"),
            ParameterSpec("video_resolution", "video_resolution", "Video resolution override."),
            ParameterSpec("poll", "poll", "Optional polling window in seconds.", value_type="int", min_value=0),
        ),
        examples=(
            'python3 .agent/skills/dreamina-cli/scripts/frames2video.py --first ./start.png --last ./end.png --prompt "season changes around the subject" --model-version seedance2.0fast',
        ),
    ),
    "multiframe2video": CommandSpec(
        name="multiframe2video",
        description="Submit a Dreamina multi-image story video task.",
        output_mode="json",
        validator=validate_multiframe2video,
        parameters=(
            ParameterSpec("images", "images", "Two to twenty local image paths.", required=True, multiple=True, csv_split=True, path_mode="file"),
            ParameterSpec("prompt", "prompt", "Shorthand prompt for exactly two images."),
            ParameterSpec("duration", "duration", "Shorthand duration for exactly two images.", value_type="float"),
            ParameterSpec("transition_prompt", "transition-prompt", "Repeat once per transition segment.", multiple=True),
            ParameterSpec("transition_duration", "transition-duration", "Repeat once per transition segment.", value_type="float", multiple=True),
            ParameterSpec("poll", "poll", "Optional polling window in seconds.", value_type="int", min_value=0),
        ),
        examples=(
            'python3 .agent/skills/dreamina-cli/scripts/multiframe2video.py --images ./a.png,./b.png --prompt "the character turns to face camera"',
            'python3 .agent/skills/dreamina-cli/scripts/multiframe2video.py --images ./a.png --images ./b.png --images ./c.png --transition-prompt "A turns into B" --transition-prompt "B turns into C"',
        ),
    ),
    "multimodal2video": CommandSpec(
        name="multimodal2video",
        description="Submit Dreamina's flagship multimodal video task.",
        output_mode="json",
        validator=validate_multimodal2video,
        parameters=(
            ParameterSpec("image", "image", "Repeat for each input image.", multiple=True, csv_split=True, path_mode="file"),
            ParameterSpec("video", "video", "Repeat for each input video.", multiple=True, csv_split=True, path_mode="file"),
            ParameterSpec("audio", "audio", "Repeat for each input audio file.", multiple=True, csv_split=True, path_mode="file"),
            ParameterSpec("prompt", "prompt", "Optional edit prompt."),
            ParameterSpec("duration", "duration", "Video duration in seconds.", value_type="int", min_value=4, max_value=15),
            ParameterSpec(
                "ratio",
                "ratio",
                "Output aspect ratio.",
                choices=("1:1", "3:4", "16:9", "4:3", "9:16", "21:9"),
            ),
            ParameterSpec("video_resolution", "video_resolution", "Video resolution.", choices=("720p",)),
            ParameterSpec(
                "model_version",
                "model_version",
                "Model version.",
                choices=("seedance2.0", "seedance2.0fast"),
            ),
            ParameterSpec("poll", "poll", "Optional polling window in seconds.", value_type="int", min_value=0),
        ),
        examples=(
            'python3 .agent/skills/dreamina-cli/scripts/multimodal2video.py --image ./scene.png --audio ./music.mp3 --model-version seedance2.0fast --duration 5',
        ),
    ),
    "query_result": CommandSpec(
        name="query_result",
        description="Query a Dreamina task by submit_id.",
        output_mode="json",
        parameters=(
            ParameterSpec("submit_id", "submit_id", "Dreamina submit_id.", required=True),
            ParameterSpec("download_dir", "download_dir", "Optional result download directory.", path_mode="dir", create_dir=True),
        ),
        examples=(
            "python3 .agent/skills/dreamina-cli/scripts/query_result.py --submit-id 3f6eb41f425d23a3",
        ),
    ),
    "list_task": CommandSpec(
        name="list_task",
        description="List Dreamina tasks for the current logged-in user.",
        output_mode="json",
        parameters=(
            ParameterSpec("submit_id", "submit_id", "Optional submit_id filter."),
            ParameterSpec("gen_status", "gen_status", "Optional generation status filter."),
            ParameterSpec("gen_task_type", "gen_task_type", "Optional task type filter."),
            ParameterSpec("limit", "limit", "Maximum tasks to return.", value_type="int", min_value=1, max_value=200),
            ParameterSpec("offset", "offset", "Pagination offset.", value_type="int", min_value=0),
        ),
        examples=(
            "python3 .agent/skills/dreamina-cli/scripts/list_task.py --gen-status success --limit 20",
        ),
    ),
    "user_credit": CommandSpec(
        name="user_credit",
        description="Query the current Dreamina account credit.",
        output_mode="json",
        examples=("python3 .agent/skills/dreamina-cli/scripts/user_credit.py",),
    ),
    "login": CommandSpec(
        name="login",
        description="Reuse the current Dreamina login session or start the browser login flow.",
        output_mode="text",
        parameters=(ParameterSpec("debug", "debug", "Show manual-import troubleshooting output.", value_type="bool"),),
        examples=("python3 .agent/skills/dreamina-cli/scripts/login.py --debug",),
    ),
    "logout": CommandSpec(
        name="logout",
        description="Clear the current Dreamina login session.",
        output_mode="text",
        examples=("python3 .agent/skills/dreamina-cli/scripts/logout.py",),
    ),
    "relogin": CommandSpec(
        name="relogin",
        description="Clear the current Dreamina session and force a fresh browser login.",
        output_mode="text",
        parameters=(ParameterSpec("debug", "debug", "Show manual-import troubleshooting output.", value_type="bool"),),
        examples=("python3 .agent/skills/dreamina-cli/scripts/relogin.py --debug",),
    ),
    "version": CommandSpec(
        name="version",
        description="Print Dreamina CLI version information.",
        output_mode="json_or_text",
        examples=("python3 .agent/skills/dreamina-cli/scripts/version.py",),
    ),
}


def build_parser(spec: CommandSpec) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{spec.name}.py",
        description=spec.description,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    for parameter in spec.parameters:
        help_text = parameter.help
        if parameter.choices:
            help_text = f"{help_text} Choices: {', '.join(parameter.choices)}."
        if parameter.min_value is not None and parameter.max_value is not None:
            help_text = f"{help_text} Range: {parameter.min_value}-{parameter.max_value}."
        elif parameter.min_value is not None:
            help_text = f"{help_text} Minimum: {parameter.min_value}."

        kwargs: dict[str, Any] = {
            "dest": parameter.key,
            "help": help_text,
            "required": False,
        }

        if parameter.value_type == "bool":
            kwargs["action"] = "store_true"
            kwargs.pop("required", None)
        else:
            kwargs["default"] = None

            if parameter.multiple:
                kwargs["action"] = "append"

            if parameter.value_type == "int":
                kwargs["type"] = int
            elif parameter.value_type == "float":
                kwargs["type"] = float
            else:
                kwargs["type"] = str

        parser.add_argument(*parameter.argument_names, **kwargs)

    parser.add_argument(
        "--dreamina-bin",
        default="dreamina",
        help="Dreamina executable path. Defaults to 'dreamina'.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print the CLI command without executing it.",
    )

    return parser


def build_cli_args(spec: CommandSpec, namespace: argparse.Namespace) -> list[str]:
    args = [spec.name]
    for parameter in spec.parameters:
        value = getattr(namespace, parameter.key)

        if value is None or value is False:
            continue

        if parameter.value_type == "bool":
            args.append(f"--{parameter.cli_flag}")
            continue

        if parameter.multiple:
            for item in value:
                args.extend((f"--{parameter.cli_flag}", stringify_value(item)))
            continue

        args.extend((f"--{parameter.cli_flag}", stringify_value(value)))

    return args


def stringify_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def run_dreamina(command: list[str]) -> tuple[str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise DreaminaWrapperError(
            f"Dreamina executable not found: {command[0]}",
            details=[str(error)],
        ) from error

    if completed.returncode != 0:
        raise normalize_exec_error(command, completed.returncode, completed.stdout, completed.stderr)

    return completed.stdout, completed.stderr


def validate_generation_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DreaminaWrapperError("Dreamina generation command returned a non-object payload.")

    submit_id = str(payload.get("submit_id", "")).strip()
    gen_status = str(payload.get("gen_status", "")).strip()

    if gen_status == "fail":
        raise DreaminaWrapperError(
            str(payload.get("fail_reason") or "Dreamina reported a failed generation task."),
            details=[json.dumps(payload, ensure_ascii=False)],
        )

    if not submit_id or gen_status not in VALID_SUBMIT_STATUSES:
        raise DreaminaWrapperError(
            "Dreamina generation response is missing submit_id or a valid submit status.",
            details=[json.dumps(payload, ensure_ascii=False)],
        )

    return payload


def format_text_payload(stdout: str, stderr: str) -> dict[str, Any]:
    return {
        "stdout": strip_ansi(stdout).strip(),
        "stderr": strip_ansi(stderr).strip(),
        "stdout_lines": compact_lines(stdout),
        "stderr_lines": compact_lines(stderr),
    }


def parse_command_output(spec: CommandSpec, stdout: str, stderr: str) -> Any:
    if spec.output_mode == "text":
        return format_text_payload(stdout, stderr)

    if spec.output_mode == "json_or_text":
        try:
            return parse_json_payload(stdout, stderr)
        except DreaminaWrapperError:
            return format_text_payload(stdout, stderr)

    payload = parse_json_payload(stdout, stderr)
    if spec.name in GENERATION_COMMANDS:
        return validate_generation_payload(payload)
    return payload


def capabilities_payload() -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    for spec in COMMAND_SPECS.values():
        commands.append(
            {
                "name": spec.name,
                "description": spec.description,
                "output_mode": spec.output_mode,
                "examples": list(spec.examples),
                "parameters": [
                    {
                        "key": parameter.key,
                        "cli_flag": parameter.cli_flag,
                        "multiple": parameter.multiple,
                        "required": parameter.required,
                        "value_type": parameter.value_type,
                        "choices": list(parameter.choices),
                        "min_value": parameter.min_value,
                        "max_value": parameter.max_value,
                        "path_mode": parameter.path_mode,
                    }
                    for parameter in spec.parameters
                ],
            }
        )

    return {
        "skill": "dreamina-cli",
        "wrapper_version": 1,
        "command_count": len(commands),
        "commands": commands,
    }


def markdown_capabilities() -> str:
    lines = ["# Dreamina Wrapper Capabilities", ""]
    for spec in COMMAND_SPECS.values():
        lines.append(f"## {spec.name}")
        lines.append(spec.description)
        lines.append("")
        if spec.parameters:
            lines.append("| Parameter | CLI Flag | Type | Required | Notes |")
            lines.append("| --- | --- | --- | --- | --- |")
            for parameter in spec.parameters:
                notes: list[str] = []
                if parameter.choices:
                    notes.append(f"choices: {', '.join(parameter.choices)}")
                if parameter.min_value is not None or parameter.max_value is not None:
                    if parameter.min_value is not None and parameter.max_value is not None:
                        notes.append(f"range: {parameter.min_value}-{parameter.max_value}")
                    elif parameter.min_value is not None:
                        notes.append(f"min: {parameter.min_value}")
                    else:
                        notes.append(f"max: {parameter.max_value}")
                if parameter.multiple:
                    notes.append("repeatable")
                if parameter.path_mode:
                    notes.append(f"path: {parameter.path_mode}")
                lines.append(
                    f"| `{parameter.key}` | `--{parameter.cli_flag}` | `{parameter.value_type}` | "
                    f"`{'yes' if parameter.required else 'no'}` | {'; '.join(notes) or '-'} |"
                )
            lines.append("")
        if spec.examples:
            lines.append("Examples:")
            for example in spec.examples:
                lines.append(f"- `{example}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main_for_command(command_name: str, argv: Sequence[str] | None = None) -> int:
    spec = COMMAND_SPECS[command_name]
    parser = build_parser(spec)
    try:
        namespace = parser.parse_args(argv)
        namespace = normalize_namespace(spec, namespace)
        validate_parameter_ranges(spec, namespace)

        if spec.validator:
            spec.validator(namespace)

        cli_args = build_cli_args(spec, namespace)
        full_command = [namespace.dreamina_bin, *cli_args]

        if namespace.dry_run:
            return json_dump(
                {
                    "ok": True,
                    "command": spec.name,
                    "dry_run": True,
                    "cli_args": full_command,
                }
            )

        stdout, stderr = run_dreamina(full_command)
        payload = parse_command_output(spec, stdout, stderr)
        return json_dump(
            {
                "ok": True,
                "command": spec.name,
                "cli_args": full_command,
                "data": payload,
            }
        )
    except DreaminaWrapperError as error:
        cli_args = build_cli_args(spec, namespace) if "namespace" in locals() else [spec.name]
        dreamina_bin = getattr(namespace, "dreamina_bin", "dreamina") if "namespace" in locals() else "dreamina"
        full_command = [dreamina_bin, *cli_args]
        return json_dump(
            {
                "ok": False,
                "command": spec.name,
                "cli_args": full_command,
                "error": error.message,
                "details": error.details,
            },
            exit_code=error.exit_code,
        )


def main_list_capabilities(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="list_capabilities.py",
        description="List Dreamina wrapper capabilities in JSON or Markdown.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format.",
    )
    args = parser.parse_args(argv)

    if args.format == "markdown":
        sys.stdout.write(markdown_capabilities())
        return 0

    return json_dump(capabilities_payload())
