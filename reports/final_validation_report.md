# Final validation report

```text
                     Metric     Baseline    Optimized    Change
  allocated_bin_utilization     0.152024     0.152024    0.0000
        allocation_coverage     0.004656     0.004656    0.0000
         average_distance_m    23.072800    22.811200   -0.2616
            complete_orders   494.000000   494.000000    0.0000
         estimated_time_min   253.818667   252.074667   -1.7440
        order_line_coverage     0.136274     0.136274    0.0000
           orders_simulated   500.000000   500.000000    0.0000
           total_distance_m 11536.400000 11405.600000 -130.8000
  unknown_hazard_attributes   150.000000   150.000000    0.0000
whole_warehouse_utilization     0.095015     0.095015    0.0000
```

Runtime seconds: 7.39

## Correctness-hardening qualification

The saved baseline and optimized allocations were independently revalidated without regenerating the pipeline. Each has 150 assignments, zero known hard-constraint violations, and zero unknown SKU/location references under the configured representative-stock and ergonomic assumptions. This is not a safety-compliance certification: all 150 assignments have unavailable observed inventory and `UNSPECIFIED` hazard and handling attributes, producing 450 unverified checks per layout. See `correctness_hardening_report.md` and its detailed validation CSVs.
