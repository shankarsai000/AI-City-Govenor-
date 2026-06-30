import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.audit.service import AuditLedgerService
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


class ProofVerificationRequest(BaseModel):
    leaf_hash: str = Field(..., min_length=64, max_length=128)
    merkle_root: str = Field(..., min_length=64, max_length=128)
    proof: list[dict[str, str]]


@router.get("/ledger")
async def search_ledger(
    event_type: str | None = Query(default=None),
    action_id: uuid.UUID | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    """Search and filter cryptographic audit ledger entries."""
    entries = await AuditLedgerService.search_entries(
        event_type=event_type,
        action_id=action_id,
        correlation_id=correlation_id,
        search=search,
        limit=limit,
    )
    return {
        "requested_by": principal.username,
        "count": len(entries),
        "results": [AuditLedgerService.serialize_entry(entry) for entry in entries],
    }


@router.get("/verify")
async def verify_ledger(
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "auditor")),
) -> dict[str, Any]:
    """Verify cryptographic integrity of the entire ledger chain (recomputes hashes & Merkle root)."""
    verification = await AuditLedgerService.verify_ledger()
    verification["requested_by"] = principal.username
    return verification


@router.get("/ledger/{entry_id}/proof")
async def get_entry_proof(
    entry_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    """Build Merkle audit proof for a specific log entry to prove its inclusion."""
    proof = await AuditLedgerService.build_entry_proof(entry_id=entry_id)
    proof["requested_by"] = principal.username
    return proof


@router.post("/verify-proof")
async def verify_proof(
    payload: ProofVerificationRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "auditor")),
) -> dict[str, Any]:
    """Verify a cryptographic Merkle proof against a root hash."""
    valid = AuditLedgerService.verify_entry_proof(
        leaf_hash=payload.leaf_hash,
        merkle_root=payload.merkle_root,
        proof=payload.proof,
    )
    return {
        "requested_by": principal.username,
        "valid": valid,
    }


@router.get("/export")
async def export_ledger(
    format: str = Query(default="json", pattern="^(json|jsonl)$"),
    event_type: str | None = Query(default=None),
    action_id: uuid.UUID | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "auditor")),
) -> Any:
    """Export audit entries (JSON or JSONL format) with Merkle root header."""
    export_payload = await AuditLedgerService.export_entries(
        event_type=event_type,
        action_id=action_id,
        correlation_id=correlation_id,
        search=search,
        limit=limit,
    )
    if format == "jsonl":
        lines = [str(export_payload["merkle_root"] or "")]
        lines.extend(
            json.dumps(entry, separators=(",", ":"), ensure_ascii=True)
            for entry in export_payload["entries"]
        )
        return PlainTextResponse("\n".join(lines), media_type="application/x-ndjson")

    export_payload["requested_by"] = principal.username
    return export_payload
