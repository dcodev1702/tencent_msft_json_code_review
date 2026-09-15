import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image
import resvg_py


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("assets", type=Path)
    parser.add_argument("--preview-dir", type=Path, required=True)
    args = parser.parse_args()
    args.preview_dir.mkdir(parents=True, exist_ok=True)
    results = []
    namespace = "{http://www.w3.org/2000/svg}"

    for source in sorted(args.assets.glob("*.svg")):
        root = ET.parse(source).getroot()
        viewbox = [float(value) for value in root.attrib["viewBox"].split()]
        width, height = int(viewbox[2]), int(viewbox[3])
        connectors = 0
        for element in root.iter():
            if "stroke-dasharray" in element.attrib:
                raise ValueError(f"Dashed element in {source.name}")
            if element.tag == namespace + "path":
                if re.search(r"[CcSsQqTtAa]", element.attrib.get("d", "")):
                    raise ValueError(f"Curved path in {source.name}")
            if element.tag in {namespace + "script", namespace + "foreignObject"}:
                raise ValueError(f"Executable/embedded HTML in {source.name}")
            if "connector" in element.attrib.get("class", "").split():
                connectors += 1
                if element.tag not in {
                    namespace + "line",
                    namespace + "polyline",
                    namespace + "path",
                }:
                    raise ValueError("Unexpected connector element")
            for name, value in element.attrib.items():
                if name.endswith("href") and not value.startswith("#"):
                    raise ValueError(f"External resource in {source.name}")
        if connectors == 0:
            raise ValueError(f"No marked connectors in {source.name}")
        if root.find(namespace + "title") is None:
            raise ValueError(f"Missing accessible title in {source.name}")
        if root.find(namespace + "desc") is None:
            raise ValueError(f"Missing accessible description in {source.name}")

        output = source.with_suffix(".png")
        output.write_bytes(resvg_py.svg_to_bytes(svg_path=str(source), zoom=2.0))
        with Image.open(output) as image:
            assert image.size == (width * 2, height * 2), (source, image.size)
            assert image.getbbox() is not None, source
            preview = image.copy()
            preview.thumbnail((1280, 1280))
            preview.save(args.preview_dir / output.name)

        results.append(
            {
                "svg": source.name,
                "png": output.name,
                "png_width": width * 2,
                "png_height": height * 2,
                "solid_straight_connectors": connectors,
            }
        )
    if not results:
        raise ValueError("No SVG diagrams found")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
