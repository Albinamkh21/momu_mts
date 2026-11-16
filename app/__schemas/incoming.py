# app/schemas/incoming.py
from typing import Annotated, Union
from pydantic import Field, TypeAdapter

from __schemas.external_contract import ExternalContractCreateRequest
from __schemas.contract_annex import IncomingAnnexPayload


IncomingPayload = Annotated[
    Union[ExternalContractCreateRequest, IncomingAnnexPayload],
    Field(discriminator="request_type"),
]

incoming_payload_adapter: TypeAdapter[IncomingPayload] = TypeAdapter(IncomingPayload)