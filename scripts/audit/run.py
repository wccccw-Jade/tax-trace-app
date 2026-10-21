"""Run from the repository root: .venv/bin/python -m scripts.audit.run"""
from backend.cli import main
if __name__ == '__main__':
    import sys
    sys.argv.insert(1, 'audit')
    main()
