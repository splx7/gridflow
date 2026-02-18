"""N-1 Contingency Analysis.

For each branch in the network, removes it, re-runs power flow, and
checks for voltage and thermal violations against the grid code
contingency limits.

Returns a list of contingency results indicating pass/fail per branch,
along with details of any violations found.

IEEE 399 / NERC TPL methodology: the system must remain stable (no
voltage collapse, no overloads beyond contingency limits) when any
single branch is out of service.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from engine.network.network_model import NetworkModel, BranchData, BusType
from engine.network.power_flow import solve_power_flow, dc_power_flow, PowerFlowResult
from engine.network.grid_codes import GridCodeProfile, IEC_DEFAULT


@dataclass
class VoltageViolationDetail:
    """A single bus voltage violation during a contingency."""
    bus_name: str
    bus_index: int
    voltage_pu: float
    limit_type: str   # "low" or "high"
    limit_value: float  # the limit that was exceeded


@dataclass
class ThermalViolationDetail:
    """A single branch thermal violation during a contingency."""
    branch_name: str
    branch_index: int
    loading_pct: float
    rating_mva: float
    limit_pct: float  # the thermal limit from the grid code


@dataclass
class ContingencyResult:
    """Result for a single N-1 contingency (one branch removed)."""
    branch_name: str
    branch_index: int
    branch_type: str
    passed: bool
    converged: bool
    iterations: int
    max_mismatch: float
    voltage_violations: list[VoltageViolationDetail] = field(default_factory=list)
    thermal_violations: list[ThermalViolationDetail] = field(default_factory=list)
    min_voltage_pu: float = 1.0
    max_voltage_pu: float = 1.0
    max_loading_pct: float = 0.0
    # If the removed branch causes islanding (disconnected buses)
    causes_islanding: bool = False


@dataclass
class ContingencyAnalysisResult:
    """Complete N-1 contingency analysis result."""
    grid_code: str
    total_contingencies: int
    passed_count: int
    failed_count: int
    island_count: int
    worst_voltage_pu: float
    worst_voltage_bus: str
    worst_loading_pct: float
    worst_loading_branch: str
    contingencies: list[ContingencyResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "grid_code": self.grid_code,
            "summary": {
                "total_contingencies": self.total_contingencies,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "islanding_cases": self.island_count,
                "worst_voltage_pu": round(self.worst_voltage_pu, 4),
                "worst_voltage_bus": self.worst_voltage_bus,
                "worst_loading_pct": round(self.worst_loading_pct, 1),
                "worst_loading_branch": self.worst_loading_branch,
                "n1_secure": self.failed_count == 0,
            },
            "contingencies": [
                {
                    "branch_name": c.branch_name,
                    "branch_index": c.branch_index,
                    "branch_type": c.branch_type,
                    "passed": c.passed,
                    "converged": c.converged,
                    "causes_islanding": c.causes_islanding,
                    "min_voltage_pu": round(c.min_voltage_pu, 4),
                    "max_voltage_pu": round(c.max_voltage_pu, 4),
                    "max_loading_pct": round(c.max_loading_pct, 1),
                    "voltage_violations": [
                        {
                            "bus_name": v.bus_name,
                            "bus_index": v.bus_index,
                            "voltage_pu": round(v.voltage_pu, 4),
                            "limit_type": v.limit_type,
                            "limit_value": v.limit_value,
                        }
                        for v in c.voltage_violations
                    ],
                    "thermal_violations": [
                        {
                            "branch_name": t.branch_name,
                            "branch_index": t.branch_index,
                            "loading_pct": round(t.loading_pct, 1),
                            "rating_mva": t.rating_mva,
                            "limit_pct": t.limit_pct,
                        }
                        for t in c.thermal_violations
                    ],
                }
                for c in self.contingencies
            ],
        }


def _remove_branch(network: NetworkModel, branch_idx: int) -> NetworkModel:
    """Create a copy of the network with one branch removed.

    Returns a new NetworkModel (does not mutate the original).
    """
    # Deep-copy buses to avoid mutating original
    new_buses = copy.deepcopy(network.buses)
    # Keep all branches except the removed one, re-index
    new_branches: list[BranchData] = []
    for br in network.branches:
        if br.index == branch_idx:
            continue
        new_br = copy.deepcopy(br)
        new_br.index = len(new_branches)
        new_branches.append(new_br)

    return NetworkModel(
        buses=new_buses,
        branches=new_branches,
        s_base_mva=network.s_base_mva,
    )


def _check_connectivity(network: NetworkModel, removed_branch: BranchData) -> bool:
    """Check if removing a branch disconnects the network (creates an island).

    Uses BFS from the slack bus to verify all buses are reachable.
    """
    n = network.n_bus
    if n <= 1:
        return True  # trivially connected

    # Build adjacency list from remaining branches
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for br in network.branches:
        # The branch has already been removed from the network copy,
        # so all branches in the model are still present
        adj[br.from_bus].add(br.to_bus)
        adj[br.to_bus].add(br.from_bus)

    # BFS from slack bus
    try:
        start = network.slack_bus
    except ValueError:
        # No slack bus -- check from bus 0
        start = 0

    visited: set[int] = set()
    queue = [start]
    visited.add(start)

    while queue:
        current = queue.pop(0)
        for neighbor in adj.get(current, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return len(visited) == n


def run_contingency_analysis(
    network: NetworkModel,
    grid_code: GridCodeProfile | None = None,
    max_iter: int = 30,
    tolerance: float = 1e-6,
) -> ContingencyAnalysisResult:
    """Run N-1 contingency analysis on the network.

    For each branch:
    1. Remove the branch from the network
    2. Check if the network becomes islanded
    3. Run power flow on the reduced network
    4. Check voltage and thermal violations against contingency limits

    Args:
        network: The base NetworkModel with current bus injections set
        grid_code: Grid code profile for violation limits. Defaults to IEC.
        max_iter: Max Newton-Raphson iterations
        tolerance: Convergence tolerance

    Returns:
        ContingencyAnalysisResult with per-branch pass/fail results
    """
    if grid_code is None:
        grid_code = IEC_DEFAULT

    contingencies: list[ContingencyResult] = []
    worst_voltage = 1.0
    worst_voltage_bus = ""
    worst_loading = 0.0
    worst_loading_branch = ""
    island_count = 0

    thermal_limit = grid_code.thermal_limit_pct

    for branch in network.branches:
        # Create reduced network
        reduced = _remove_branch(network, branch.index)

        # Check connectivity
        is_connected = _check_connectivity(reduced, branch)

        if not is_connected:
            island_count += 1
            contingencies.append(ContingencyResult(
                branch_name=branch.name,
                branch_index=branch.index,
                branch_type=branch.branch_type,
                passed=False,
                converged=False,
                iterations=0,
                max_mismatch=float("inf"),
                causes_islanding=True,
                min_voltage_pu=0.0,
                max_voltage_pu=0.0,
                max_loading_pct=0.0,
            ))
            continue

        # Solve power flow
        pf_result = solve_power_flow(reduced, max_iter=max_iter, tolerance=tolerance)
        if not pf_result.converged:
            pf_result = dc_power_flow(reduced)

        # Check voltage violations against contingency limits
        voltage_violations: list[VoltageViolationDetail] = []
        min_v = float("inf")
        max_v = 0.0

        for bus in reduced.buses:
            v = float(pf_result.voltage_pu[bus.index])
            min_v = min(min_v, v)
            max_v = max(max_v, v)

            violation = grid_code.voltage.check_contingency(v)
            if violation is not None:
                limit_val = (
                    grid_code.voltage.contingency_min
                    if violation == "low"
                    else grid_code.voltage.contingency_max
                )
                voltage_violations.append(VoltageViolationDetail(
                    bus_name=bus.name,
                    bus_index=bus.index,
                    voltage_pu=v,
                    limit_type=violation,
                    limit_value=limit_val,
                ))

            # Track global worst
            if v < worst_voltage:
                worst_voltage = v
                worst_voltage_bus = bus.name

        # Check thermal violations
        thermal_violations: list[ThermalViolationDetail] = []
        max_loading = 0.0

        for bf in pf_result.branch_flows:
            loading = bf.loading_pct
            max_loading = max(max_loading, loading)

            if loading > thermal_limit:
                # Find the branch rating from the reduced network
                rating_mva = 0.0
                for br in reduced.branches:
                    if br.index == bf.branch_index:
                        rating_mva = br.rating_mva
                        break

                thermal_violations.append(ThermalViolationDetail(
                    branch_name=bf.branch_name,
                    branch_index=bf.branch_index,
                    loading_pct=loading,
                    rating_mva=rating_mva,
                    limit_pct=thermal_limit,
                ))

            if loading > worst_loading:
                worst_loading = loading
                worst_loading_branch = bf.branch_name

        passed = (
            pf_result.converged
            and len(voltage_violations) == 0
            and len(thermal_violations) == 0
        )

        contingencies.append(ContingencyResult(
            branch_name=branch.name,
            branch_index=branch.index,
            branch_type=branch.branch_type,
            passed=passed,
            converged=pf_result.converged,
            iterations=pf_result.iterations,
            max_mismatch=pf_result.max_mismatch,
            voltage_violations=voltage_violations,
            thermal_violations=thermal_violations,
            min_voltage_pu=min_v if min_v != float("inf") else 0.0,
            max_voltage_pu=max_v,
            max_loading_pct=max_loading,
            causes_islanding=False,
        ))

    passed_count = sum(1 for c in contingencies if c.passed)
    failed_count = len(contingencies) - passed_count

    return ContingencyAnalysisResult(
        grid_code=grid_code.name,
        total_contingencies=len(contingencies),
        passed_count=passed_count,
        failed_count=failed_count,
        island_count=island_count,
        worst_voltage_pu=worst_voltage,
        worst_voltage_bus=worst_voltage_bus,
        worst_loading_pct=worst_loading,
        worst_loading_branch=worst_loading_branch,
        contingencies=contingencies,
    )
