import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


OLD = "&GetInvalidSchemaPointer().GetAllocator()"
NEW = "&GetStateAllocator()"
BODY = """void EndMissingDependentProperties(const SValue& sourceName) {
    PointerType schemaRef = GetInvalidSchemaPointer().Append(
        keyword, &GetInvalidSchemaPointer().GetAllocator());
    AddErrorSchemaLocation(error, schemaRef.Append(
        sourceName.GetString(), sourceName.GetStringLength(),
        &GetInvalidSchemaPointer().GetAllocator()));
}
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmake", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    cmake = args.cmake.resolve(strict=True)
    patch = args.patch.resolve(strict=True)
    results = []

    def run(label, source=None):
        command = [str(cmake)]
        if source is not None:
            command.append(f"-DSOURCE_DIR={source}")
        command.extend(["-P", str(patch)])
        process = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=30
        )
        result = {
            "test": label,
            "return_code": process.returncode,
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
        }
        results.append(result)
        return result

    with tempfile.TemporaryDirectory(
        prefix="patch-cases-", dir=args.output.parent
    ) as temporary:
        root = Path(temporary)
        result = run("missing_source_dir")
        assert result["return_code"] != 0, result
        assert "SOURCE_DIR must be defined" in result["stderr"], result

        result = run("missing_schema_file", root / "does-not-exist")
        assert result["return_code"] != 0, result
        assert "schema.h not found" in result["stderr"], result

        source = root / "source"
        header = source / "include" / "rapidjson" / "schema.h"
        header.parent.mkdir(parents=True)
        header.write_text(BODY, encoding="utf-8", newline="")
        result = run("two_matching_calls", source)
        actual = header.read_text(encoding="utf-8")
        assert result["return_code"] == 0, result
        assert actual == BODY.replace(OLD, NEW), result
        result["before_matches"] = BODY.count(OLD)
        result["after_old_matches"] = actual.count(OLD)
        result["after_new_matches"] = actual.count(NEW)

        first_hash = hashlib.sha256(header.read_bytes()).hexdigest()
        result = run("second_run_is_idempotent", source)
        assert result["return_code"] == 0, result
        assert hashlib.sha256(header.read_bytes()).hexdigest() == first_hash
        assert "already applied or pattern not found" in result["stdout"], result
        result["bytes_unchanged"] = True

        drifted = BODY.replace(
            OLD, "&GetInvalidSchemaPointer( ).GetAllocator()"
        )
        header.write_text(drifted, encoding="utf-8", newline="")
        result = run("zero_match_source_drift", source)
        assert result["return_code"] == 0, result
        assert header.read_text(encoding="utf-8") == drifted
        assert "already applied or pattern not found" in result["stdout"], result
        result["unmodified_drifted_source_returns_success"] = True

        extra = BODY + f"void unrelated() {{ use({OLD}); }}\n"
        header.write_text(extra, encoding="utf-8", newline="")
        result = run("third_call_outside_target_function", source)
        actual = header.read_text(encoding="utf-8")
        assert result["return_code"] == 0, result
        assert actual == extra.replace(OLD, NEW)
        result["before_matches"] = extra.count(OLD)
        result["after_new_matches"] = actual.count(NEW)

        marker = root / "must-not-be-created.txt"
        literal = (
            '// ${VARIABLE_THAT_MUST_REMAIN_LITERAL}; C++ punctuation\n'
            f'// file(WRITE "{marker.as_posix()}" "not executed")\n'
        )
        header.write_text(BODY + literal, encoding="utf-8", newline="")
        result = run("header_contents_remain_data", source)
        assert result["return_code"] == 0, result
        assert header.read_text(encoding="utf-8") == BODY.replace(OLD, NEW) + literal
        assert not marker.exists()
        result["literal_text_preserved"] = True
        result["embedded_cmake_text_not_executed"] = True

    evidence = {
        "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
        "cmake_version": subprocess.run(
            [str(cmake), "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.splitlines()[0],
        "all_expectations_met": True,
        "results": results,
    }
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
