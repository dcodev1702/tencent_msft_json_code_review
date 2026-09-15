# Tencent/Microsoft RapidJSON allocator review

The completed, bounded security review is in
[`docs/rapidjson-allocator-security-review.md`](docs/rapidjson-allocator-security-review.md).

It assesses the two allocator substitutions in
`EndMissingDependentProperties()` and the CMake script that applies them, with
reproducible focused harnesses and dark-neon architecture diagrams.
