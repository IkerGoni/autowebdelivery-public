"""TemplateParser - Extracts sections from Stitch-generated HTML into standalone snippets.

Parses HTML files using section comment markers, extracts Tailwind config,
and creates parameterized templates with {{mustache}} placeholders.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Base directory for this module
MODULE_DIR = Path(__file__).parent
ARTIFACTS_DIR = MODULE_DIR.parent.parent / "stitch-artifacts"

# Section extraction patterns - comment markers used in the HTML files
# Maps section_name -> list of possible comment patterns to match
SECTION_MARKERS = {
    "header": [
        r"<!--\s*TopNavBar\s*-->",
        r"<!--\s*TopAppBar\s*-->",
        r"<!--\s*Top\s*App\s*Bar\s*-->",
        r"<!--\s*Top\s*Navigation\s*Shell\s*-->",
    ],
    "hero": [
        r"<!--\s*Section\s*1:\s*Hero\s*-->",
        r"<!--\s*Hero\s*Section\s*-->",
        r"<!--\s*Editorial\s*Hero\s*-->",
    ],
    "services": [
        r"<!--\s*Section\s*2:\s*Service\s*Overview\s*.*?-->",
        r"<!--\s*Section\s*2:\s*Treatment\s*Categories\s*-->",
        r"<!--\s*Service\s*Categories\s*-->",
        r"<!--\s*Treatment\s*Categories\s*-->",
        r"<!--\s*Services\s*Grid\s*-->",
        r"<!--\s*Services\s*Section\s*-->",
    ],
    "trust": [
        r"<!--\s*Section\s*3:\s*Trust\s*Section\s*-->",
        r"<!--\s*Trust\s*Section\s*-->",
    ],
    "location": [
        r"<!--\s*Section\s*4\s*&\s*5:\s*Location.*?-->",
        r"<!--\s*Location\s*&\s*Hours\s*-->",
        r"<!--\s*Location\s*&\s*Hours\s*Section\s*-->",
        r"<!--\s*Map\s*Section\s*-->",
    ],
    "cta": [
        r"<!--\s*Section\s*6:\s*Contact\s*CTA\s*-->",
        r"<!--\s*CTA\s*Section\s*-->",
        r"<!--\s*Contact\s*CTA\s*-->",
        r"<!--\s*Contact\s*Section\s*-->",
        r"<!--\s*Section\s*6:\s*Final\s*CTA\s*-->",
    ],
    "footer": [
        r"<!--\s*Footer\s*-->",
    ],
}

# Known section end markers (the next section starts, or EOF)
SECTION_ORDER = ["header", "hero", "services", "trust", "location", "cta", "footer"]


class TemplateParser:
    """Parses Stitch-generated HTML templates into modular sections."""

    def __init__(self, artifacts_dir: Optional[Path] = None):
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR

    def _read_file(self, family: str, variant: str) -> str:
        """Read an HTML file from the artifacts directory."""
        filename = "index.html" if variant == "desktop" else "mobile.html"
        path = self.artifacts_dir / family / filename
        if not path.exists():
            raise FileNotFoundError(f"No {variant} HTML for {family}: {path}")
        return path.read_text(encoding="utf-8")

    def _extract_tailwind_config(self, html: str) -> str:
        """Extract the tailwind.config block from HTML."""
        match = re.search(
            r'<script[^>]*id=["\']tailwind-config["\'][^>]*>\s*(tailwind\.config\s*=\s*\{.*?\})\s*</script>',
            html,
            re.DOTALL,
        )
        if not match:
            # Try without id
            match = re.search(
                r'<script>\s*(tailwind\.config\s*=\s*\{.*?\})\s*</script>',
                html,
                re.DOTALL,
            )
        return match.group(1) if match else ""

    def _extract_style_blocks(self, html: str) -> str:
        """Extract all <style> blocks from HTML."""
        styles = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL)
        return "\n".join(styles)

    def _extract_font_links(self, html: str) -> List[str]:
        """Extract Google Fonts link tags."""
        return re.findall(r'<link[^>]*fonts\.googleapis\.com[^>]*/>', html)

    def _extract_head_content(self, html: str) -> str:
        """Extract everything between <head> and </head>."""
        match = re.search(r"<head[^>]*>(.*?)</head>", html, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _find_section_ranges(self, html: str) -> Dict[str, Tuple[int, int]]:
        """Find start/end positions of each section in the HTML."""
        ranges = {}
        section_starts = []

        for section_name, patterns in SECTION_MARKERS.items():
            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    section_starts.append((match.start(), section_name))
                    break

        # Sort by position in document
        section_starts.sort(key=lambda x: x[0])

        # Find the end of each section (start of next section, or end of main/footer)
        for i, (start_pos, name) in enumerate(section_starts):
            if i + 1 < len(section_starts):
                end_pos = section_starts[i + 1][0]
            else:
                # Last section - find </body> or use end of string
                body_end = html.find("</body>")
                end_pos = body_end if body_end != -1 else len(html)
            ranges[name] = (start_pos, end_pos)

        return ranges

    def _extract_section_html(self, html: str, section_name: str) -> Optional[str]:
        """Extract raw HTML for a named section."""
        ranges = self._find_section_ranges(html)
        if section_name not in ranges:
            return None
        start, end = ranges[section_name]
        section_html = html[start:end].strip()

        # Remove the comment marker itself
        section_html = re.sub(r"<!--\s*.*?-->\s*\n?", "", section_html, count=1)
        return section_html.strip()

    def _parameterize(self, html: str, family: str) -> str:
        """Replace hardcoded business data with {{mustache}} placeholders."""
        # This is family-aware because each family has different hardcoded data
        # We do generic replacements based on patterns

        # Common business name patterns
        replacements = [
            # Phone numbers in tel: links and display
            (r'href="tel:[^"]*"', 'href="tel:{{phone_raw}}"'),
            (r'href="tel:\+?1?[^\d]*(\d[\d\-]+)"', 'href="tel:{{phone_raw}}"'),
            # Various phone display formats
            (r'\(123\)\s*456-7890', '{{phone}}'),
            (r'\(555\)\s*012-3456', '{{phone}}'),
            (r'1-800-LUXE-GLO', '{{phone}}'),
            (r'555\.0123', '{{phone}}'),
            (r'555-012-3456', '{{phone}}'),
            (r'\(555\)\s*012-3456', '{{phone}}'),
            (r'123\*\*\*\*\*7890', '{{phone}}'),
        ]

        for pattern, replacement in replacements:
            html = re.sub(pattern, replacement, html)

        return html

    def parse_family(self, family: str) -> Dict:
        """Parse all sections and config for a template family.

        Returns dict with:
          - config: dict with tailwind_config, styles, font_links
          - sections: dict[section_name] -> dict with desktop, mobile HTML
        """
        result = {
            "config": {},
            "sections": {},
        }

        for variant in ["desktop", "mobile"]:
            try:
                html = self._read_file(family, variant)
            except FileNotFoundError:
                continue

            suffix = "" if variant == "desktop" else "_mobile"

            if variant == "desktop":
                # Extract config from desktop version
                result["config"] = {
                    "tailwind_config": self._extract_tailwind_config(html),
                    "styles": self._extract_style_blocks(html),
                    "font_links": self._extract_font_links(html),
                }

            # Extract each section
            for section_name in SECTION_ORDER:
                section_html = self._extract_section_html(html, section_name)
                if section_html:
                    key = f"{section_name}{suffix}"
                    result["sections"][key] = section_html

        return result

    def extract_and_save(self, family: str, output_dir: Optional[Path] = None) -> List[Path]:
        """Extract all sections for a family and save to files.

        Returns list of created file paths.
        """
        output_dir = output_dir or MODULE_DIR / "sections" / family
        output_dir.mkdir(parents=True, exist_ok=True)

        parsed = self.parse_family(family)
        created = []

        # Save config
        config_dir = MODULE_DIR / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / f"{family}.json"

        # Parse tailwind config into structured JSON
        config_data = self._parse_config_to_json(parsed["config"], family)
        config_path.write_text(json.dumps(config_data, indent=2, ensure_ascii=False))
        created.append(config_path)

        # Save sections
        for key, html in parsed["sections"].items():
            section_path = output_dir / f"{key}.html"
            section_path.write_text(html, encoding="utf-8")
            created.append(section_path)

        return created

    def _parse_config_to_json(self, config: Dict, family: str) -> Dict:
        """Convert raw config strings into structured JSON."""
        tw_config_str = config.get("tailwind_config", "")

        # Extract the JS object from tailwind.config = {...}
        match = re.search(r"tailwind\.config\s*=\s*(\{.*\})\s*$", tw_config_str, re.DOTALL | re.MULTILINE)
        config_obj = {}
        if match:
            js_obj = match.group(1)
            # Quick JS->Python: unquoted keys, trailing commas, single quotes
            # Use a simple approach - extract known sections via regex
            config_obj = self._js_object_to_python(js_obj)

        return {
            "family": family,
            "tailwind_config_raw": tw_config_str,
            "colors": config_obj.get("colors", {}),
            "borderRadius": config_obj.get("borderRadius", {}),
            "spacing": config_obj.get("spacing", {}),
            "fontFamily": config_obj.get("fontFamily", {}),
            "fontSize": config_obj.get("fontSize", {}),
            "styles": config.get("styles", ""),
            "font_links": config.get("font_links", []),
        }

    def _js_object_to_python(self, js: str) -> Dict:
        """Rough conversion of JS config object to Python dict."""
        result = {}

        # Extract top-level extend keys
        # Look for "colors": {...}, "borderRadius": {...}, etc.
        for key in ["colors", "borderRadius", "spacing", "fontFamily", "fontSize"]:
            pattern = rf'"{key}"\s*:\s*(\{{[^}}]*(?:\{{[^}}]*\}}[^}}]*)*\}})'
            match = re.search(pattern, js, re.DOTALL)
            if match:
                obj_str = match.group(1)
                result[key] = self._parse_js_dict(obj_str)

        return result

    def _parse_js_dict(self, s: str) -> Dict:
        """Parse a simple JS dict string into Python dict."""
        result = {}
        # Remove outer braces
        s = s.strip()
        if s.startswith("{"):
            s = s[1:]
        if s.endswith("}"):
            s = s[:-1]

        # Match "key": "value" or "key": ["value"]
        for match in re.finditer(r'"([^"]+)"\s*:\s*(?:"([^"]*)"|\[([^\]]*)\]|\{([^}]*)\})', s):
            key = match.group(1)
            if match.group(2) is not None:
                result[key] = match.group(2)
            elif match.group(3) is not None:
                # Array - parse items
                items = re.findall(r'"([^"]*)"', match.group(3))
                result[key] = items if items else match.group(3)
            elif match.group(4) is not None:
                result[key] = match.group(4)

        return result


def parse_all_families() -> Dict[str, List[Path]]:
    """Parse all 4 template families and save to disk.

    Returns dict mapping family name -> list of created files.
    """
    parser = TemplateParser()
    results = {}
    for family in ["clinical-trust", "warm-editorial", "industrial-reliable", "fresh-utility"]:
        try:
            results[family] = parser.extract_and_save(family)
        except Exception as e:
            print(f"Warning: Failed to parse {family}: {e}")
            results[family] = []
    return results


if __name__ == "__main__":
    results = parse_all_families()
    for family, paths in results.items():
        print(f"\n{family}: {len(paths)} files created")
        for p in paths:
            print(f"  {p}")
