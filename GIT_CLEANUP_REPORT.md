# Git Cleanup Report

The following incorrectly tracked files were removed from the Git index to maintain a clean repository state:

- `dataset/output.csv` (Duplicate output tracked in dataset directory)
- `dataset/images/sample/.DS_Store`
- `dataset/images/sample/case_003/.DS_Store`
- `dataset/images/test/.DS_Store`
- `dataset/images/test/case_007/.DS_Store`
- `dataset/images/test/case_010/.DS_Store`

These files were removed using `git rm --cached` so local copies are preserved but they will no longer be tracked.
