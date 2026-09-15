import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    allocator = json.loads((root / "allocator-results.json").read_text())
    patch = json.loads((root / "quoted-patch-results.json").read_text())
    records = {
        (record["revision"], record["mode"], record["case"]): record
        for record in allocator["results"]
    }
    outcomes = []
    cases = sorted({record["case"] for record in allocator["results"]})
    for case in cases:
        item = {"case": case}
        for revision in ["original", "patched"]:
            for mode in ["optimized", "sanitized"]:
                record = records[revision, mode, case]
                expected_failure = mode == "sanitized" and (
                    case == "empty-pointer"
                    or (revision == "original" and case in {"root-invalid", "escaped-invalid"})
                )
                assert record["return_code"] == (1 if expected_failure else 0), record
                if expected_failure:
                    assert "reference binding to null pointer" in record["stderr"], record
                    result = "UBSan null-reference diagnostic; configured halt, exit 1"
                else:
                    assert not record["stderr"], record
                    result = "exit 0; expected validation outcome; no diagnostic"
                if case == "empty-pointer" and not expected_failure:
                    result = "exit 0; prints allocator address 0; no diagnostic"
                item[f"{revision}_{mode}"] = result
        if case != "empty-pointer":
            original = records["original", "optimized", case]["stdout"]
            patched = records["patched", "optimized", case]["stdout"]
            assert original == patched, case
            assert patched == records["patched", "sanitized", case]["stdout"], case
            item["optimized_outputs_byte_identical"] = True
            item["validation_output"] = json.loads(patched)
        outcomes.append(item)

    source = root / "rapidjson-original"
    pin = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    original_header = (source / "include" / "rapidjson" / "schema.h").read_bytes()
    patched_header = (
        root / "rapidjson-patched" / "include" / "rapidjson" / "schema.h"
    ).read_bytes()
    old = b"&GetInvalidSchemaPointer().GetAllocator()"
    new = b"&GetStateAllocator()"
    assert original_header.count(old) == 2
    assert patched_header == original_header.replace(old, new)

    script = root / "upstream-fix-null-allocator-deref.cmake"
    patch_source = (
        "upstream script verified against the quoted input"
        if script.exists()
        else "user-quoted CMake script"
    )
    if script.exists():
        assert script.read_bytes().replace(b"\r\n", b"\n") == (
            root / "quoted-fix-null-allocator-deref.cmake"
        ).read_bytes().replace(b"\r\n", b"\n")

    evidence = {
        "assessment_date": "2026-09-14",
        "rapidjson_repository": "https://github.com/Tencent/rapidjson",
        "rapidjson_commit": pin,
        "scope": "Focused allocator and literal-patch tests, not an SDK build or whole-repository audit",
        "compiler": allocator["compiler"],
        "platform": allocator["platform"],
        "standard": allocator["standard"],
        "optimized_flags": allocator["optimized_flags"],
        "sanitized_flags": allocator["sanitized_flags"],
        "patch_source": patch_source,
        "patch_sha256": patch["patch_sha256"],
        "cmake_version": patch["cmake_version"],
        "source_hashes": allocator["source_hashes"],
        "exactly_two_intended_header_substitutions": True,
        "all_32_allocator_run_expectations_met": True,
        "all_seven_patch_fixture_expectations_met": patch["all_expectations_met"],
        "allocator_outcomes": outcomes,
        "patch_outcomes": [
            {key: value for key, value in row.items() if key not in {"stderr", "stdout"}}
            for row in patch["results"]
        ],
        "negative_control": (
            "empty-pointer directly calls GetAllocator() outside the modified schema path; "
            "its sanitizer failure is expected before and after this targeted patch"
        ),
        "reproducer_sha256": hashlib.sha256(
            (root / "allocator_probe.cpp").read_bytes()
        ).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"All expectations met; evidence saved to {args.output}")


if __name__ == "__main__":
    main()
