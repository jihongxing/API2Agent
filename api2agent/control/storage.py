import sqlite3
from pathlib import Path
from typing import Any
import json

from api2agent.capabilities.models import MetricsSnapshot, RoutingDecision
from api2agent.control.models import UsageEvent, UsageLedgerRow, UsageSummary


USAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_events (
  id TEXT PRIMARY KEY,
  routing_decision_id TEXT,
  execution_mode TEXT NOT NULL DEFAULT 'proxy',
  project_id TEXT NOT NULL,
  capability_id TEXT NOT NULL,
  provider_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  method TEXT NOT NULL,
  path TEXT NOT NULL,
  status_code INTEGER,
  success INTEGER NOT NULL,
  latency_ms REAL NOT NULL,
  estimated_cost REAL NOT NULL,
  error_type TEXT,
  created_at TEXT NOT NULL
);
"""

ROUTING_DECISION_SCHEMA = """
CREATE TABLE IF NOT EXISTS routing_decisions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  capability_id TEXT NOT NULL,
  strategy TEXT NOT NULL,
  preset TEXT,
  selected_provider_id TEXT,
  ranked_provider_ids TEXT NOT NULL,
  metrics TEXT NOT NULL,
  failover_policy TEXT,
  created_at TEXT NOT NULL
);
"""


class UsageStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(USAGE_SCHEMA)
            connection.execute(ROUTING_DECISION_SCHEMA)
            self._ensure_usage_column(connection, "routing_decision_id", "TEXT")
            self._ensure_usage_column(connection, "execution_mode", "TEXT NOT NULL DEFAULT 'proxy'")
            self._ensure_routing_decision_column(connection, "failover_policy", "TEXT")

    def record(self, event: UsageEvent) -> UsageEvent:
        data = event.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO usage_events (
                  id, routing_decision_id, execution_mode, project_id, capability_id, provider_id, tool_id,
                  method, path, status_code, success, latency_ms,
                  estimated_cost, error_type, created_at
                ) VALUES (
                  :id, :routing_decision_id, :execution_mode, :project_id, :capability_id, :provider_id, :tool_id,
                  :method, :path, :status_code, :success, :latency_ms,
                  :estimated_cost, :error_type, :created_at
                )
                """,
                {**data, "success": 1 if event.success else 0},
            )
        return event

    def record_routing_decision(self, decision: RoutingDecision) -> RoutingDecision:
        data = decision.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO routing_decisions (
                  id, project_id, capability_id, strategy, preset,
                  selected_provider_id, ranked_provider_ids, metrics, failover_policy, created_at
                ) VALUES (
                  :id, :project_id, :capability_id, :strategy, :preset,
                  :selected_provider_id, :ranked_provider_ids, :metrics, :failover_policy, :created_at
                )
                """,
                {
                    **data,
                    "ranked_provider_ids": json.dumps(data["ranked_provider_ids"], ensure_ascii=False),
                    "metrics": json.dumps(data["metrics"], ensure_ascii=False),
                    "failover_policy": json.dumps(data["failover_policy"], ensure_ascii=False)
                    if data.get("failover_policy") is not None
                    else None,
                },
            )
        return decision

    def get_routing_decision(self, decision_id: str) -> RoutingDecision | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM routing_decisions WHERE id = ?",
                (decision_id,),
            ).fetchone()

        if row is None:
            return None

        data = dict(row)
        data["ranked_provider_ids"] = json.loads(data["ranked_provider_ids"])
        data["metrics"] = json.loads(data["metrics"])
        data["failover_policy"] = json.loads(data["failover_policy"]) if data.get("failover_policy") else None
        return RoutingDecision.model_validate(data)

    def usage_for_routing_decision(self, decision_id: str) -> list[UsageEvent]:
        with self._connect() as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM usage_events WHERE routing_decision_id = ? ORDER BY created_at",
                    (decision_id,),
                ).fetchall()
            ]
        return [UsageEvent.model_validate({**row, "success": bool(row["success"])}) for row in rows]

    def get_usage_event(self, event_id: str) -> UsageEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM usage_events WHERE id = ?",
                (event_id,),
            ).fetchone()

        if row is None:
            return None

        data = dict(row)
        return UsageEvent.model_validate({**data, "success": bool(data["success"])})

    def count(self, project_id: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM usage_events"
        params: tuple[Any, ...] = ()
        if project_id:
            query += " WHERE project_id = ?"
            params = (project_id,)

        with self._connect() as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def summarize(self, project_id: str | None = None) -> UsageSummary:
        query = "SELECT * FROM usage_events"
        params: tuple[Any, ...] = ()
        if project_id:
            query += " WHERE project_id = ?"
            params = (project_id,)

        with self._connect() as connection:
            rows = [dict(row) for row in connection.execute(query, params).fetchall()]

        total = len(rows)
        successful = sum(1 for row in rows if row["success"])
        failed = total - successful
        average_latency = sum(float(row["latency_ms"]) for row in rows) / total if total else 0.0
        estimated_cost = sum(float(row["estimated_cost"]) for row in rows)
        error_counts: dict[str, int] = {}
        for row in rows:
            error_type = row["error_type"]
            if error_type:
                error_counts[error_type] = error_counts.get(error_type, 0) + 1

        return UsageSummary(
            project_id=project_id,
            total_calls=total,
            successful_calls=successful,
            failed_calls=failed,
            success_rate=successful / total if total else 0.0,
            average_latency_ms=average_latency,
            estimated_cost=estimated_cost,
            error_counts=error_counts,
        )

    def ledger(
        self,
        project_id: str | None = None,
        capability_id: str | None = None,
        provider_id: str | None = None,
        month: str | None = None,
        group_by_mode: bool = False,
    ) -> list[UsageLedgerRow]:
        group_fields = ["project_id", "capability_id", "provider_id"]
        if group_by_mode:
            group_fields.append("execution_mode")
        group_sql = ", ".join(group_fields)
        query = """
            SELECT
              project_id,
              capability_id,
              provider_id,
              {execution_mode_select}
              COUNT(*) AS total_calls,
              SUM(success) AS successful_calls,
              AVG(latency_ms) AS average_latency_ms,
              SUM(estimated_cost) AS estimated_cost
            FROM usage_events
        """.format(execution_mode_select="execution_mode," if group_by_mode else "NULL AS execution_mode,")
        clauses: list[str] = []
        params: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if capability_id:
            clauses.append("capability_id = ?")
            params.append(capability_id)
        if provider_id:
            clauses.append("provider_id = ?")
            params.append(provider_id)
        if month:
            clauses.append("substr(created_at, 1, 7) = ?")
            params.append(month)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += f" GROUP BY {group_sql} ORDER BY {group_sql}"

        with self._connect() as connection:
            rows = [dict(row) for row in connection.execute(query, tuple(params)).fetchall()]

        ledger_rows: list[UsageLedgerRow] = []
        for row in rows:
            total_calls = int(row["total_calls"] or 0)
            successful_calls = int(row["successful_calls"] or 0)
            ledger_rows.append(
                UsageLedgerRow(
                    project_id=str(row["project_id"]),
                    capability_id=str(row["capability_id"]),
                    provider_id=str(row["provider_id"]),
                    execution_mode=row["execution_mode"],
                    total_calls=total_calls,
                    successful_calls=successful_calls,
                    failed_calls=total_calls - successful_calls,
                    success_rate=successful_calls / total_calls if total_calls else 0.0,
                    average_latency_ms=float(row["average_latency_ms"] or 0.0),
                    estimated_cost=float(row["estimated_cost"] or 0.0),
                )
            )
        return ledger_rows

    def metrics_for_capability(self, capability_id: str) -> list[MetricsSnapshot]:
        with self._connect() as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT
                      capability_id,
                      provider_id,
                      COUNT(*) AS total_calls,
                      SUM(success) AS successful_calls,
                      AVG(latency_ms) AS average_latency_ms,
                      AVG(estimated_cost) AS estimated_cost_per_call
                    FROM usage_events
                    WHERE capability_id = ?
                    GROUP BY capability_id, provider_id
                    """,
                    (capability_id,),
                ).fetchall()
            ]

        snapshots: list[MetricsSnapshot] = []
        for row in rows:
            total_calls = int(row["total_calls"] or 0)
            successful_calls = int(row["successful_calls"] or 0)
            failed_calls = total_calls - successful_calls
            snapshots.append(
                MetricsSnapshot(
                    capability_id=str(row["capability_id"]),
                    provider_id=str(row["provider_id"]),
                    total_calls=total_calls,
                    successful_calls=successful_calls,
                    failed_calls=failed_calls,
                    success_rate=successful_calls / total_calls if total_calls else 0.0,
                    average_latency_ms=float(row["average_latency_ms"] or 0.0),
                    estimated_cost_per_call=float(row["estimated_cost_per_call"] or 0.0),
                )
            )
        return snapshots

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_usage_column(self, connection: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(usage_events)").fetchall()}
        if name not in columns:
            connection.execute(f"ALTER TABLE usage_events ADD COLUMN {name} {definition}")

    def _ensure_routing_decision_column(self, connection: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(routing_decisions)").fetchall()}
        if name not in columns:
            connection.execute(f"ALTER TABLE routing_decisions ADD COLUMN {name} {definition}")
