#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys


COMMANDS = {
    "root": [],
    "help": ["help"],
    "text2image": ["text2image"],
    "image2image": ["image2image"],
    "image_upscale": ["image_upscale"],
    "text2video": ["text2video"],
    "image2video": ["image2video"],
    "frames2video": ["frames2video"],
    "multiframe2video": ["multiframe2video"],
    "multimodal2video": ["multimodal2video"],
    "query_result": ["query_result"],
    "list_task": ["list_task"],
    "user_credit": ["user_credit"],
    "login": ["login"],
    "login_checklogin": ["login", "checklogin"],
    "logout": ["logout"],
    "relogin": ["relogin"],
    "session": ["session"],
    "session_create": ["session", "create"],
    "session_list": ["session", "list"],
    "session_ls": ["session", "ls"],
    "session_search": ["session", "search"],
    "session_find": ["session", "find"],
    "session_rename": ["session", "rename"],
    "session_update": ["session", "update"],
    "session_delete": ["session", "delete"],
    "session_rm": ["session", "rm"],
    "version": ["version"],
}


def read_help(args: list[str]) -> str:
    result = subprocess.run(
        ["dreamina", *args, "-h"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dreamina {' '.join(args)} -h failed: {result.stderr.strip()}")
    return f"{result.stdout}\n{result.stderr}"


def require(outputs: dict[str, str], command: str, text: str) -> None:
    if text not in outputs[command]:
        raise AssertionError(f"{command} help is missing {text!r}")


def reject(outputs: dict[str, str], command: str, text: str) -> None:
    if text in outputs[command]:
        raise AssertionError(f"{command} help still contains retired value {text!r}")


def main() -> int:
    outputs = {name: read_help(args) for name, args in COMMANDS.items()}

    for name in (
        "text2image", "image2image", "image_upscale", "text2video",
        "image2video", "frames2video", "multiframe2video", "multimodal2video",
        "query_result", "list_task", "user_credit", "login", "logout",
        "relogin", "session", "version",
    ):
        require(outputs, "root", name)

    for name in ("text2image", "image2image"):
        require(outputs, name, "5.0Pro")
        require(outputs, name, "--generate_num")
        require(outputs, name, "--width")
        require(outputs, name, "--height")
        require(outputs, name, "--resolution_type is required")

    require(outputs, "image_upscale", "--resolution_type is required")
    for name in ("text2video", "image2video", "frames2video", "multimodal2video"):
        require(outputs, name, "seedance2.5")
        require(outputs, name, "--video_resolution")
        require(outputs, name, "video_resolution 720p, 1080p, or 4k")

    require(outputs, "image2video", "default model_version: seedance2.0_vip")
    require(outputs, "frames2video", "default model_version: seedance2.0_vip")
    require(outputs, "multimodal2video", "default model_version: seedance2.0_vip")
    require(outputs, "multimodal2video", "audio-only is allowed")
    require(outputs, "multiframe2video", "supported range: 1-8")
    require(outputs, "multiframe2video", "--video_resolution")
    reject(outputs, "image2video", "3.0_fast")
    reject(outputs, "frames2video", "3.5_pro")

    require(outputs, "login", "OAuth Device Flow")
    require(outputs, "login_checklogin", "--device_code")
    for name in ("session_list", "session_ls"):
        require(outputs, name, "--max-count")
    for name in ("session_search", "session_find"):
        require(outputs, name, "dreamina session search <name>")
    for name in ("session_rename", "session_update"):
        require(outputs, name, "dreamina session rename <session_id> <new_name>")
    for name in ("session_delete", "session_rm"):
        require(outputs, name, "dreamina session delete <session_id>")

    print(f"Dreamina CLI help audit passed ({len(COMMANDS)} commands checked)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError) as error:
        print(f"Dreamina CLI help audit failed: {error}", file=sys.stderr)
        raise SystemExit(1)
