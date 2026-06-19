def preview():
    """Dry-run: what memory_max would Press compute for each active bench on press-f1
    if we flip set_bench_memory_limits=True?"""
    import frappe
    SERVER = "press-f1.sandbox.mvpstorm.com"
    GUNICORN_MEM = 150  # MB per worker
    BG_MEM = 240        # MB per worker (3 * 80 default)
    benches = frappe.db.sql(
        """SELECT name, `group`, gunicorn_workers, background_workers,
                  memory_high, memory_max, memory_swap, status
           FROM `tabBench`
           WHERE server = %s AND status = 'Active'
           ORDER BY name""",
        (SERVER,), as_dict=True,
    )
    lines = [f"ACTIVE BENCHES ON {SERVER}: {len(benches)}", ""]
    lines.append(f"{'BENCH':<40} {'GUN':>3} {'BG':>3} {'CURRENT_MAX':>11} {'PROPOSED_MAX':>13} {'SWAP':>11}")
    total_max = 0
    total_swap = 0
    for b in benches:
        g = b.gunicorn_workers or 2
        bg = b.background_workers or 1
        memory_high = 512 + (g * GUNICORN_MEM) + (bg * BG_MEM)
        memory_max = memory_high + GUNICORN_MEM + BG_MEM
        memory_swap = memory_max * 2
        total_max += memory_max
        total_swap += memory_swap
        lines.append(f"{b.name:<40} {g:>3} {bg:>3} {b.memory_max or 0:>10}M {memory_max:>12}M {memory_swap:>10}M")
    lines.append("")
    lines.append(f"TOTAL PROPOSED memory_max:  {total_max} MB = {total_max/1024:.1f} GB")
    lines.append(f"TOTAL PROPOSED memory_swap: {total_swap} MB = {total_swap/1024:.1f} GB")
    lines.append("")
    lines.append("Host has ~16 GB RAM + 4 GB swap. If sum-of-max > host RAM, expect cgroup OOM under load.")
    print("\n".join(lines))
