from typing import Any

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.ml import (
    FeatureSchema,
    PredictRequest,
    TrainRequest,
    get_anomaly_detection_service,
    get_feature_names,
)
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


@router.post("/train")
async def train_anomaly_model(
    payload: TrainRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    service = get_anomaly_detection_service()
    result = await run_in_threadpool(service.train_from_simulation_run, payload)
    return {
        "requested_by": principal.username,
        "result": result.model_dump(mode="json"),
    }


@router.post("/predict")
async def predict_anomaly(
    payload: PredictRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    service = get_anomaly_detection_service()
    prediction = await run_in_threadpool(service.predict, payload)
    return {
        "requested_by": principal.username,
        "prediction": prediction.model_dump(mode="json"),
    }


@router.get("/model")
async def get_model_info(
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    service = get_anomaly_detection_service()
    info = await run_in_threadpool(service.get_model_info)
    return {
        "requested_by": principal.username,
        "model": info.model_dump(mode="json"),
    }


@router.get("/models")
async def list_model_versions(
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    service = get_anomaly_detection_service()
    versions = await run_in_threadpool(service.list_model_versions)
    return {
        "requested_by": principal.username,
        "count": len(versions),
        "results": [version.model_dump(mode="json") for version in versions],
    }


@router.get("/features")
async def get_feature_schema(
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    schema = FeatureSchema(
        feature_count=len(get_feature_names()),
        feature_names=get_feature_names(),
    )
    return {
        "requested_by": principal.username,
        "schema": schema.model_dump(mode="json"),
    }
