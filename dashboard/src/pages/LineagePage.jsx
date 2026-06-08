import { useQuery } from "@tanstack/react-query";
import { getLineageGraph } from "../services/api";

export default function LineagePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["lineage"],
    queryFn: getLineageGraph,
  });

  if (isLoading) return <p>Loading lineage graph...</p>;

  return (
    <div>
      <h2>Data Lineage</h2>
      <p style={{ color: "#6b7280", marginBottom: "1rem" }}>
        Showing {data?.nodes?.length} nodes and {data?.edges?.length} edges in the pipeline.
      </p>
      <div className="lineage-table">
        <h3>Nodes</h3>
        <table className="table">
          <thead><tr><th>ID</th><th>Label</th><th>Type</th></tr></thead>
          <tbody>
            {data?.nodes?.map((n) => (
              <tr key={n.id}>
                <td><code>{n.id}</code></td>
                <td>{n.label}</td>
                <td><span className={`badge badge-${n.type}`}>{n.type}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        <h3 style={{ marginTop: "1.5rem" }}>Edges</h3>
        <table className="table">
          <thead><tr><th>From</th><th>Relationship</th><th>To</th></tr></thead>
          <tbody>
            {data?.edges?.map((e, i) => (
              <tr key={i}>
                <td><code>{e.source}</code></td>
                <td>{e.label}</td>
                <td><code>{e.target}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
