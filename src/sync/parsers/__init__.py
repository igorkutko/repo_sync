"""Odoo file parsers for chunking content."""

from repo_sync.sync.parsers.generic_parser import parse_generic_file
from repo_sync.sync.parsers.manifest_parser import parse_manifest
from repo_sync.sync.parsers.python_parser import parse_python_file
from repo_sync.sync.parsers.xml_parser import parse_xml_file

__all__ = [
    "parse_manifest",
    "parse_python_file",
    "parse_xml_file",
    "parse_generic_file",
]
