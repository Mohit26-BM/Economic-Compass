import axios from "axios";

const client = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || "http://localhost:8000") + "/api",
});

// Pipeline
export const getSeries = () => client.get("/pipeline/series").then((r) => r.data);
export const getSeriesData = (id, limit = 120) =>
  client.get(`/pipeline/series/${id}`, { params: { limit } }).then((r) => r.data);

// Metrics
export const getAllDrift = (refMonths = 60, curMonths = 6) =>
  client.get("/metrics/drift", { params: { reference_months: refMonths, current_months: curMonths } }).then((r) => r.data);
export const getDriftReport = (id, refMonths = 60, curMonths = 6) =>
  client.get(`/metrics/drift/${id}`, { params: { reference_months: refMonths, current_months: curMonths } }).then((r) => r.data);
export const getForecast = (id, horizon = 12) =>
  client.get(`/metrics/forecast/${id}`, { params: { horizon } }).then((r) => r.data);

// Lineage
export const getLineageGraph = () => client.get("/lineage/graph").then((r) => r.data);

// Analysis
export const getRecession = () => client.get("/analysis/recession").then((r) => r.data);
export const getCorrelation = () => client.get("/analysis/correlation").then((r) => r.data);
export const getRegime = () => client.get("/analysis/regime").then((r) => r.data);
export const getTaylorRule = () => client.get("/analysis/taylor").then((r) => r.data);
export const getCalibration = (id) =>
  client.get(`/analysis/calibration/${id}`).then((r) => r.data);
export const getSahm = () => client.get("/analysis/sahm").then((r) => r.data);
export const getConditions = () => client.get("/analysis/conditions").then((r) => r.data);
export const getSimulateDefaults = () => client.get("/analysis/simulate-defaults").then((r) => r.data);
export const runSimulation = (inputs) => client.post("/analysis/simulate", inputs).then((r) => r.data);
