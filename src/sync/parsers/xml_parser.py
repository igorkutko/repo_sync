"""lxml-based parser for Odoo XML files (views, data, templates)."""

from __future__ import annotations

import logging
from pathlib import Path

from lxml import etree

from models import ChunkType, CollectionName, ContentChunk

logger = logging.getLogger(__name__)


def _element_to_string(element: etree._Element) -> str:
    """Serialize an XML element back to a string."""
    return etree.tostring(element, pretty_print=True, encoding="unicode")


def _extract_view_type(record: etree._Element) -> str | None:
    """Try to determine the view type from a record element."""
    # <field name="type">form</field>
    for field in record.findall(".//field[@name='type']"):
        if field.text:
            return field.text.strip()
    # <field name="arch"><form>... → infer from root tag of arch
    for arch_field in record.findall(".//field[@name='arch']"):
        for child in arch_field:
            return child.tag  # e.g. "form", "tree", "kanban"
    return None


def _extract_view_model(record: etree._Element) -> str | None:
    """Try to determine the model from a record element."""
    for field in record.findall(".//field[@name='model']"):
        if field.text:
            return field.text.strip()
    # Check model attribute on the record itself
    return record.get("model")


def parse_xml_file(
    file_path: Path,
    repo_name: str,
    module_name: str,
    rel_path: str,
) -> list[ContentChunk]:
    """Parse an Odoo XML file into chunks (one per record/template/menuitem)."""
    try:
        source = file_path.read_bytes()
    except Exception:
        logger.warning("Cannot read file: %s", file_path)
        return []

    try:
        parser = etree.XMLParser(recover=True, remove_comments=True)
        tree = etree.fromstring(source, parser=parser)
    except Exception:
        logger.warning("Failed to parse XML: %s", file_path)
        return []

    if tree is None:
        return []

    chunks: list[ContentChunk] = []

    # Process <record> elements
    for record in tree.iter("record"):
        xml_id = record.get("id", "")
        model = record.get("model", "")
        content = _element_to_string(record)
        view_type = _extract_view_type(record)
        view_model = _extract_view_model(record) or model

        chunk_type = ChunkType.XML_RECORD
        chunk_name = xml_id or f"record_{model}"

        sourceline = record.sourceline or 1
        line_count = content.count("\n") + 1

        chunks.append(
            ContentChunk(
                repo_name=repo_name,
                module_name=module_name,
                file_path=rel_path,
                chunk_type=chunk_type,
                chunk_name=chunk_name,
                start_line=sourceline,
                end_line=sourceline + line_count - 1,
                content=content,
                collection=CollectionName.VIEWS,
                xml_id=xml_id or None,
                view_type=view_type,
                view_model=view_model or None,
            )
        )

    # Process <template> elements
    for template in tree.iter("template"):
        xml_id = template.get("id", "")
        content = _element_to_string(template)
        chunk_name = xml_id or "template"

        sourceline = template.sourceline or 1
        line_count = content.count("\n") + 1

        chunks.append(
            ContentChunk(
                repo_name=repo_name,
                module_name=module_name,
                file_path=rel_path,
                chunk_type=ChunkType.XML_TEMPLATE,
                chunk_name=chunk_name,
                start_line=sourceline,
                end_line=sourceline + line_count - 1,
                content=content,
                collection=CollectionName.VIEWS,
                xml_id=xml_id or None,
            )
        )

    # Process <menuitem> elements
    for menu in tree.iter("menuitem"):
        xml_id = menu.get("id", "")
        content = _element_to_string(menu)
        chunk_name = xml_id or "menuitem"

        sourceline = menu.sourceline or 1
        line_count = content.count("\n") + 1

        chunks.append(
            ContentChunk(
                repo_name=repo_name,
                module_name=module_name,
                file_path=rel_path,
                chunk_type=ChunkType.XML_MENUITEM,
                chunk_name=chunk_name,
                start_line=sourceline,
                end_line=sourceline + line_count - 1,
                content=content,
                collection=CollectionName.VIEWS,
                xml_id=xml_id or None,
            )
        )

    return chunks
