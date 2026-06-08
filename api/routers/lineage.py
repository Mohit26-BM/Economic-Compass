from fastapi import APIRouter

from monitoring.lineage.tracker import LineageEdge, LineageGraph, LineageNode

router = APIRouter()

# Build the static lineage graph for this pipeline
def build_pipeline_lineage() -> LineageGraph:
    g = LineageGraph()
    nodes = [
        LineageNode("fred_api",         "FRED API",                 "source"),
        LineageNode("raw_indicators",   "raw.economic_indicators",  "source"),
        LineageNode("stg_indicators",   "stg_economic_indicators",  "transform"),
        LineageNode("mart_trends",      "mart_indicator_trends",    "transform"),
        LineageNode("prophet_model",    "Prophet Forecast Model",   "model"),
        LineageNode("drift_detector",   "PSI Drift Detector",       "model"),
        LineageNode("api_forecast",     "GET /metrics/forecast",    "output"),
        LineageNode("api_drift",        "GET /metrics/drift",       "output"),
    ]
    for node in nodes:
        g.add_node(node)

    edges = [
        LineageEdge("fred_api",       "raw_indicators",  "feeds"),
        LineageEdge("raw_indicators", "stg_indicators",  "transforms"),
        LineageEdge("stg_indicators", "mart_trends",     "transforms"),
        LineageEdge("mart_trends",    "prophet_model",   "trains"),
        LineageEdge("mart_trends",    "drift_detector",  "trains"),
        LineageEdge("prophet_model",  "api_forecast",    "serves"),
        LineageEdge("drift_detector", "api_drift",       "serves"),
    ]
    for edge in edges:
        g.add_edge(edge)

    return g


@router.get("/graph")
def get_lineage_graph():
    return build_pipeline_lineage().to_dict()
