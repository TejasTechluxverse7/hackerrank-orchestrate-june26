# Files Excluded

The following items are deliberately excluded from tracking to keep the repository clean, secure, and compliant with best practices:

- `__pycache__/` and `*.pyc`: Compiled python binaries are platform-dependent and cause merge conflicts.
- `.venv/` / `venv/`: Virtual environments are local to the development machine and extremely large.
- `*.log`: Execution logs and chat transcripts (e.g. `log.txt`) are dynamically generated and should not bloat the repository history.
- `output.csv` (historical instances): Only the final canonical `output.csv` is tracked.
- `.env` / `*.key`: Secrets and API keys must never be committed to source control.
- `dataset/`: Large data assets that are already provided by the hackathon runner are not tracked if modified locally to prevent massive diffs, unless specifically required.
- Temporary files (`.DS_Store`, `Thumbs.db`, `.idea/`, `.vscode/`): IDE and OS specific metadata.
