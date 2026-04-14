"""ReadLoop v2 -- Agent Harness for Paper Research

Backward-compatible entry point. Prefer `readloop` CLI or `python -m readloop`.

    python run.py                    # Interactive mode
    python run.py --help             # Script mode options
"""
from readloop._run import main

if __name__ == "__main__":
    main()
