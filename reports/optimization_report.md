# Optimization report

Heuristic feasible reassignment; no global optimality claim.

{
  "iterations": 1,
  "heuristic": "feasible weighted distance/affinity greedy reassignment",
  "objective_weights": {
    "distance": 1.0,
    "affinity": 0.25,
    "ergonomic": 0.1,
    "waste": 1e-05
  },
  "affinity_pairs_available": 62,
  "affinity_pairs_used": 62,
  "local_search": {
    "starting_distance_m": 1883.6,
    "final_distance_m": 1840.4,
    "accepted_swaps": 1,
    "attempted_swaps": 100,
    "max_swap_attempts": 100,
    "max_passes": 1,
    "passes_completed": 1,
    "search_terminated_by_limit": true
  },
  "candidate_layouts": {
    "baseline": {
      "total_route_distance_m": 1816.3999999999999,
      "known_violations": 0
    },
    "greedy": {
      "total_route_distance_m": 1883.6,
      "known_violations": 0
    },
    "refined": {
      "total_route_distance_m": 1840.4,
      "known_violations": 0
    }
  },
  "selected_layout": "baseline",
  "selection_reason": "baseline has the lowest total simulated route distance among feasible candidates"
}
