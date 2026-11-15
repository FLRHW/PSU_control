# First-time local setup

The GitHub repository was scaffolded with folders and documentation, but its application code is delivered separately in the accompanying release ZIP. On the Kubuntu workstation, use these commands from a terminal:

```bash
cd /mnt/Data/01_Engineering/01_Projects/300_CPX400DP_control/PSU_control
# This folder must be empty before clone; confirm using ls -la.
git clone https://github.com/FLRHW/PSU_control.git .
```

Extract `PSU_control_v13_3.zip` to a temporary directory, then merge the release files into the newly cloned working tree:

```bash
mkdir -p /tmp/psu_import_v13_3
unzip -q ~/Downloads/PSU_control_v13_3.zip -d /tmp/psu_import_v13_3
cp -a /tmp/psu_import_v13_3/PSU_control_v13_3/. ./
```

The `cp` deliberately replaces the *scaffold* README and placeholder files with the release content. Nothing in the existing repository has project history yet. Do not run the copy command against a repository containing unrelated changes.

Verify and commit:

```bash
PYTHONPATH=scripts python3 -m unittest discover -s tests -p 'test_*.py'
git status --short
git add README.md .gitignore scripts/ profiles/ tests/ docs/ reports/.gitkeep
git commit -m "Import CPX400DP controller v13.3"
git push -u origin main
```

The generated reports directory remains untracked apart from its `.gitkeep` placeholder. Your original v13.2 ZIP and test history can be archived separately, without committing large reports.

Start the app:

```bash
python3 scripts/cpx400dp_gui.py
```
