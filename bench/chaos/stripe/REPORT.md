# Stripe slice chaos (offline, Prism)

Date: 2026-10-17. Plan target T3, reduced to what is cheap without Docker: a slice (customers list/retrieve/create) of the public `stripe/openapi` spec3.json,
OLD = tag v1000 (info.version 2024-04-10), NEW = master at download time (2026-09-30.endive). Slices built by `slice_spec.py` (ref closure; 835 KB and 1.15 MB). Real diff of the
slice (`diff_customers.py`): POST /v1/customers lost `coupon`, `promotion_code` and gained `business_name`, `individual_name`; list and retrieve did not change. No real Stripe calls, no key
(fake `sk_test_` string only against loopback). `cases.yaml` sha256 prefix `eabe8d7bea302f2a`, written before the run.

Result: the gateway never finished starting. **Every case is HUNG** because `openapi_loader.resolve_refs` inlines the Stripe component graph without memoisation (exponential), see
`proof/loader_probe_output.txt` (still running after 170 s of CPU on the 835 KB slice, no network involved) and SUMMARY.md bug B6. So the real Stripe version diff could not be exercised;
the NEW slice never reached Prism-backed calls. The full 8 MB spec files were not kept (re-download from the URLs in this report).

No LLM was used anywhere: no `claude -p`, no NVIDIA/OpenRouter key (stripped from every child env), the healer always ran
with `--no-repair`. Calls go through the healer's MCP front door (python `mcp` client, Streamable HTTP). The healer's heal deadline
is 30 s (`src/healer/settings.py`). Every process started was stopped; logs were scanned for key patterns (none found; the only
credential-like strings are the fake test values `k-test-123` and `sk_test_chaos_fake_not_a_real_key`).

## Every case

| Case | Expected | Observed | Verdict | Category | Note |
|---|---|---|---|---|---|
| ST1_post_customers_exposed | not_exposed | startup_hang | HUNG | hung | gateway did not open its port in 120 s (port 8103 did not open in 120s); process alive=True; cause: healer.openapi_loader.resolve_refs inlines the Stripe slice without memoisation (see loader_probe_output.txt) |
| ST2_get_customer_exposed | exposed | startup_hang | HUNG | hung | gateway did not open its port in 120 s (port 8103 did not open in 120s); process alive=True; cause: healer.openapi_loader.resolve_refs inlines the Stripe slice without memoisation (see loader_probe_output.txt) |
| ST3_list_customers_exposed | not_exposed | startup_hang | HUNG | hung | gateway did not open its port in 120 s (port 8103 did not open in 120s); process alive=True; cause: healer.openapi_loader.resolve_refs inlines the Stripe slice without memoisation (see loader_probe_output.txt) |
| ST4_retrieve_across_real_version_diff | pass_through | startup_hang | HUNG | hung | gateway did not open its port in 120 s (port 8103 did not open in 120s); process alive=True; cause: healer.openapi_loader.resolve_refs inlines the Stripe slice without memoisation (see loader_probe_output.txt) |
