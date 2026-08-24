"""Dictionary Registry — declarative config for the Generic Admin Engine.

Maps a public "dict_key" (used in the URL) to an ORM model plus the rules
needed to run generic list/search/create/update/delete operations against it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Type

from models import Label, RightCategory, RightUsageType, FindingSource, Region, Partners


@dataclass(frozen=True)
class DictionaryConfig:
    model: Type
    # Fields used for the global ILIKE search (must be text columns on the model)
    search_fields: tuple[str, ...] = ()
    # Column used to order results
    order_by: str = "id"
    # Fields the client is not allowed to set via create/update payloads
    read_only_fields: frozenset[str] = field(default_factory=lambda: frozenset({"id"}))


DICTIONARY_REGISTRY: dict[str, DictionaryConfig] = {
    "labels": DictionaryConfig(
        model=Label,
        search_fields=("name", "code"),
        order_by="name",
    ),
    "right_categories": DictionaryConfig(
        model=RightCategory,
        search_fields=("name",),
        order_by="name",
    ),
    "right_usage_types": DictionaryConfig(
        model=RightUsageType,
        search_fields=("code", "name", "description"),
        order_by="code",
    ),
    "finding_sources": DictionaryConfig(
        model=FindingSource,
        search_fields=("code", "name", "description"),
        order_by="code",
    ),
    "regions": DictionaryConfig(
        model=Region,
        search_fields=("code", "name", "description"),
        order_by="code",
    ),
    "partners": DictionaryConfig(
        model=Partners,
        search_fields=("organization_name", "service_name", "code"),
        order_by="organization_name",
    ),
}


def get_dictionary_config(dict_key: str) -> DictionaryConfig | None:
    return DICTIONARY_REGISTRY.get(dict_key)
