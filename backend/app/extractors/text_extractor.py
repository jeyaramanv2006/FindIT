"""
TextExtractor for Plain Text, Markdown, Source Code, and Config files.
Extracts content with 1-indexed line tracking and heading/symbol hierarchy.
"""

import re
from pathlib import Path
from typing import List, Optional
from app.core import config
from app.extractors.base import BaseExtractor, ExtractedBlock, ExtractedDocument


class TextExtractor(BaseExtractor):
    """
    Extracts text from UTF-8/plain text documents, Markdown files,
    source code, and structured configuration files.
    """

    SUPPORTED_EXTS = {
        ".txt",
        ".md",
        ".markdown",
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".html",
        ".css",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
    }

    @classmethod
    def supported_extensions(cls) -> set[str]:
        return cls.SUPPORTED_EXTS

    def extract(self, file_path: Path) -> ExtractedDocument:
        target = Path(file_path).resolve()
        canonical_str = str(target).replace("\\", "/")
        ext = target.suffix.lower()
        file_type = config.get_file_type(ext)

        if not target.exists():
            return ExtractedDocument(
                file_path=canonical_str,
                filename=target.name,
                extension=ext,
                file_type=file_type,
                extraction_status="ERROR",
                error_message=f"File not found: {target}",
            )

        # Read file with UTF-8, fallback to Latin-1
        try:
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(target, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception as e:
                return ExtractedDocument(
                    file_path=canonical_str,
                    filename=target.name,
                    extension=ext,
                    file_type=file_type,
                    extraction_status="ERROR",
                    error_message=f"Encoding error: {e}",
                )
        except Exception as e:
            return ExtractedDocument(
                file_path=canonical_str,
                filename=target.name,
                extension=ext,
                file_type=file_type,
                extraction_status="ERROR",
                error_message=f"Failed to read file: {e}",
            )

        lines = content.splitlines()
        total_lines = len(lines)

        if not content.strip():
            return ExtractedDocument(
                file_path=canonical_str,
                filename=target.name,
                extension=ext,
                file_type=file_type,
                blocks=[],
                total_lines=total_lines,
                extraction_status="NO_TEXT",
            )

        # Format-specific parsing
        if ext in {".md", ".markdown"}:
            blocks = self._extract_markdown(lines)
        elif file_type == "code":
            blocks = self._extract_code(lines)
        elif file_type == "config":
            blocks = self._extract_config(lines)
        else:
            blocks = self._extract_plain_text(lines)

        return ExtractedDocument(
            file_path=canonical_str,
            filename=target.name,
            extension=ext,
            file_type=file_type,
            blocks=blocks,
            total_lines=total_lines,
            extraction_status="OK" if blocks else "NO_TEXT",
        )

    def _extract_markdown(self, lines: List[str]) -> List[ExtractedBlock]:
        """
        Parses Markdown with heading hierarchy tracking.
        Groups paragraphs or list blocks while preserving line numbers.
        """
        blocks: List[ExtractedBlock] = []
        heading_stack: List[str] = []
        current_block_lines: List[str] = []
        block_start_line = 1

        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for idx, line in enumerate(lines, start=1):
            heading_match = heading_pattern.match(line.strip())
            if heading_match:
                # Flush previous block if any
                if current_block_lines:
                    text = "\n".join(current_block_lines).strip()
                    if text:
                        heading_label = " > ".join(heading_stack) if heading_stack else None
                        end_line = idx - 1
                        loc_val = f"Lines {block_start_line}–{end_line}"
                        if heading_label:
                            loc_val += f" · {heading_label}"
                        blocks.append(
                            ExtractedBlock(
                                text=text,
                                location_type="lines",
                                location_value=loc_val,
                                start_line=block_start_line,
                                end_line=end_line,
                                section_heading=heading_label,
                            )
                        )
                    current_block_lines = []

                # Update heading stack
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                if len(heading_stack) >= level:
                    heading_stack = heading_stack[:level - 1]
                heading_stack.append(title)
                block_start_line = idx
                current_block_lines.append(line)
            else:
                if not current_block_lines:
                    if line.strip():  # Start of new content block
                        block_start_line = idx
                        current_block_lines.append(line)
                else:
                    current_block_lines.append(line)
                    # Split on multiple blank lines to keep blocks modular
                    if len(current_block_lines) > 40 and not line.strip():
                        text = "\n".join(current_block_lines).strip()
                        if text:
                            heading_label = " > ".join(heading_stack) if heading_stack else None
                            loc_val = f"Lines {block_start_line}–{idx}"
                            if heading_label:
                                loc_val += f" · {heading_label}"
                            blocks.append(
                                ExtractedBlock(
                                    text=text,
                                    location_type="lines",
                                    location_value=loc_val,
                                    start_line=block_start_line,
                                    end_line=idx,
                                    section_heading=heading_label,
                                )
                            )
                        current_block_lines = []

        # Flush final block
        if current_block_lines:
            text = "\n".join(current_block_lines).strip()
            if text:
                heading_label = " > ".join(heading_stack) if heading_stack else None
                end_line = len(lines)
                loc_val = f"Lines {block_start_line}–{end_line}"
                if heading_label:
                    loc_val += f" · {heading_label}"
                blocks.append(
                    ExtractedBlock(
                        text=text,
                        location_type="lines",
                        location_value=loc_val,
                        start_line=block_start_line,
                        end_line=end_line,
                        section_heading=heading_label,
                    )
                )

        return blocks

    def _extract_code(self, lines: List[str]) -> List[ExtractedBlock]:
        """
        Parses source code into structured line-mapped blocks.
        Detects top-level functions or classes as section headings.
        """
        blocks: List[ExtractedBlock] = []
        current_lines: List[str] = []
        start_line = 1
        current_symbol: Optional[str] = None
        current_class: Optional[str] = None

        top_pattern = re.compile(
            r"^(?:def|class|async\s+def|function|export\s+(?:async\s+)?function|export\s+class|interface|type)\s+([A-Za-z0-9_]+)"
        )
        method_pattern = re.compile(
            r"^\s+(?:def|async\s+def)\s+([A-Za-z0-9_]+)"
        )

        for idx, line in enumerate(lines, start=1):
            top_match = top_pattern.match(line)
            method_match = method_pattern.match(line)

            if top_match:
                sym = top_match.group(1)
                # Flush previous block if we have accumulated lines
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text:
                        end_line = idx - 1
                        loc_val = f"Lines {start_line}–{end_line}"
                        if current_symbol:
                            loc_val += f" · {current_symbol}"
                        blocks.append(
                            ExtractedBlock(
                                text=text,
                                location_type="lines",
                                location_value=loc_val,
                                start_line=start_line,
                                end_line=end_line,
                                section_heading=current_symbol,
                            )
                        )
                    current_lines = []
                    start_line = idx

                if "class " in line:
                    current_class = sym
                else:
                    current_class = None
                current_symbol = sym
            elif method_match and current_class:
                current_symbol = f"{current_class}.{method_match.group(1)}"

            if not current_lines and not line.strip():
                start_line = idx + 1
                continue

            current_lines.append(line)

            # Flush roughly every 35-50 lines on blank line or natural break
            if len(current_lines) >= 40 and (not line.strip() or idx == len(lines)):
                text = "\n".join(current_lines).strip()
                if text:
                    loc_val = f"Lines {start_line}–{idx}"
                    if current_symbol:
                        loc_val += f" · {current_symbol}"
                    blocks.append(
                        ExtractedBlock(
                            text=text,
                            location_type="lines",
                            location_value=loc_val,
                            start_line=start_line,
                            end_line=idx,
                            section_heading=current_symbol,
                        )
                    )
                current_lines = []
                start_line = idx + 1

        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                end_line = len(lines)
                loc_val = f"Lines {start_line}–{end_line}"
                if current_symbol:
                    loc_val += f" · {current_symbol}"
                blocks.append(
                    ExtractedBlock(
                        text=text,
                        location_type="lines",
                        location_value=loc_val,
                        start_line=start_line,
                        end_line=end_line,
                        section_heading=current_symbol,
                    )
                )

        return blocks

    def _extract_config(self, lines: List[str]) -> List[ExtractedBlock]:
        """
        Parses structured configs (JSON, YAML, TOML) preserving line windows.
        """
        blocks: List[ExtractedBlock] = []
        current_lines: List[str] = []
        start_line = 1

        for idx, line in enumerate(lines, start=1):
            if not current_lines and not line.strip():
                start_line = idx + 1
                continue

            current_lines.append(line)

            if len(current_lines) >= 40 and (not line.strip() or idx == len(lines)):
                text = "\n".join(current_lines).strip()
                if text:
                    blocks.append(
                        ExtractedBlock(
                            text=text,
                            location_type="lines",
                            location_value=f"Lines {start_line}–{idx}",
                            start_line=start_line,
                            end_line=idx,
                        )
                    )
                current_lines = []
                start_line = idx + 1

        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                blocks.append(
                    ExtractedBlock(
                        text=text,
                        location_type="lines",
                        location_value=f"Lines {start_line}–{len(lines)}",
                        start_line=start_line,
                        end_line=len(lines),
                    )
                )

        return blocks

    def _extract_plain_text(self, lines: List[str]) -> List[ExtractedBlock]:
        """
        Parses plain text by paragraph grouping with line range tracking.
        """
        blocks: List[ExtractedBlock] = []
        current_lines: List[str] = []
        start_line = 1

        for idx, line in enumerate(lines, start=1):
            if not line.strip():
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text:
                        end_line = idx - 1
                        blocks.append(
                            ExtractedBlock(
                                text=text,
                                location_type="lines",
                                location_value=f"Lines {start_line}–{end_line}",
                                start_line=start_line,
                                end_line=end_line,
                            )
                        )
                    current_lines = []
                start_line = idx + 1
            else:
                current_lines.append(line)

        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                blocks.append(
                    ExtractedBlock(
                        text=text,
                        location_type="lines",
                        location_value=f"Lines {start_line}–{len(lines)}",
                        start_line=start_line,
                        end_line=len(lines),
                    )
                )

        return blocks
