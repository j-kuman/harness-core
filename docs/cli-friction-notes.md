# CLI friction notes

- Task 0 has no dogfood run under `.agent-runs/` yet, so it is easy to lose track of whether the operator step has actually started.
- PowerShell JSON quoting for `harness append --payload` is likely to be the sharpest edge; single-quoted JSON is readable, but mistakes will fail late at append time.
- PowerShell 5.1 can mangle inline JSON passed to native CLI wrappers; `harness append --payload` repeatedly received invalid JSON even when the variable printed correctly in the shell.
- Additive mitigation shipped during Task 0: use `--payload-file` or `--payload-stdin` for Windows/demo workflows instead of inline JSON.
- `harness --help` lists commands cleanly, but the Task 0 event sequence still has to be reconstructed from the packet rather than from a short in-repo operator checklist.
- `append` requires both the run id positional argument and the optional `--root` if the run root changes; that split is clear architecturally but easy to mistype during a live hand-edit session.
