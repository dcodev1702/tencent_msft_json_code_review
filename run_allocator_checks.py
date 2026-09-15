import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


CASES = [
    "root-invalid",
    "nested-invalid",
    "valid",
    "trigger-absent",
    "escaped-invalid",
    "schema-dependency-invalid",
    "ordinary-required-invalid",
    "empty-pointer",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--patched", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compiler = shutil.which("g++")
    if compiler is None:
        raise RuntimeError("g++ is required for the allocator validation")
    workspace = Path(__file__).resolve().parent
    probe = workspace / "allocator_probe.cpp"
    build = workspace / "binaries"
    build.mkdir(exist_ok=True)
    results = []
    environments = dict(os.environ)
    environments["UBSAN_OPTIONS"] = "print_stacktrace=1:halt_on_error=1"
    environments["ASAN_OPTIONS"] = "detect_leaks=1:halt_on_error=1"
    source_hashes = {}

    for revision, source in [("original", args.original), ("patched", args.patched)]:
        source = source.resolve(strict=True)
        source_hashes[revision] = {
            name: hashlib.sha256(
                (source / "include" / "rapidjson" / name).read_bytes()
            ).hexdigest()
            for name in ["schema.h", "pointer.h"]
        }
        for mode, flags in [
            ("optimized", ["-O2", "-DNDEBUG"]),
            (
                "sanitized",
                [
                    "-O1",
                    "-g",
                    "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=undefined",
                    "-fno-omit-frame-pointer",
                ],
            ),
        ]:
            binary = build / f"{revision}-{mode}"
            command = [
                compiler,
                "-std=c++11",
                *flags,
                "-I",
                str(source / "include"),
                str(probe),
                "-o",
                str(binary),
            ]
            compiled = subprocess.run(
                command, capture_output=True, text=True, check=False, timeout=120
            )
            if compiled.returncode != 0:
                raise RuntimeError(
                    f"Compilation failed for {revision}/{mode}:\n"
                    f"{compiled.stdout}\n{compiled.stderr}"
                )
            for case in CASES:
                process = subprocess.run(
                    [str(binary), case],
                    capture_output=True,
                    text=True,
                    env=environments,
                    check=False,
                    timeout=30,
                )
                record = {
                    "revision": revision,
                    "mode": mode,
                    "case": case,
                    "return_code": process.returncode,
                    "stdout": process.stdout.strip(),
                    "stderr": process.stderr.strip(),
                }
                results.append(record)
                diagnostic = (
                    process.stderr.splitlines()[0] if process.stderr else "(none)"
                )
                print(
                    f"{revision:8} {mode:9} {case:27} "
                    f"exit={process.returncode:3} {diagnostic}",
                    flush=True,
                )

    evidence = {
        "compiler": subprocess.run(
            [compiler, "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.splitlines()[0],
        "platform": os.uname().sysname + " " + os.uname().release,
        "standard": "C++11",
        "optimized_flags": "-O2 -DNDEBUG",
        "sanitized_flags": (
            "-O1 -g -fsanitize=address,undefined "
            "-fno-sanitize-recover=undefined -fno-omit-frame-pointer"
        ),
        "source_hashes": source_hashes,
        "results": results,
    }
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
