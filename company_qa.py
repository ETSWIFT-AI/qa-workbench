"""Optional company QA capabilities alongside tester.py and advanced.py."""
import argparse
import asyncio
import json
from pathlib import Path
from company.reports import save


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('workflow', 'load', 'accessibility'):
        command = sub.add_parser(name); command.add_argument('config'); command.add_argument('--output', default='reports/company-' + name)
        if name == 'workflow':
            command.add_argument('--allow-actions', action='store_true'); command.add_argument('--workers', type=int, default=2); command.add_argument('--repeats', type=int, default=1)
        if name == 'load': command.add_argument('--allow-load', action='store_true')
    security = sub.add_parser('security'); security.add_argument('directory'); security.add_argument('--ecosystems', nargs='+', choices=['npm', 'python'], default=['npm']); security.add_argument('--output', default='reports/company-security')
    manage = sub.add_parser('manage'); manage.add_argument('action', choices=['case', 'review', 'import', 'export', 'serve']); manage.add_argument('--file'); manage.add_argument('--db', default='reports/company.db'); manage.add_argument('--port', type=int, default=8780); manage.add_argument('--output', default='reports/management.json')
    args = p.parse_args(argv)
    try:
        if args.command == 'manage':
            from company.management import execute, serve
            if args.action == 'serve': serve(args.db, args.port); return 0
            data = json.loads(Path(args.file).read_text(encoding='utf-8')) if args.file else None
            result = execute(args.db, args.action, data)
            output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2), encoding='utf-8')
            print('Management export: ' + str(output)); return 0
        if args.command == 'security':
            from company.security import dependency_scan
            report = dependency_scan(args.directory, args.ecosystems, args.output)
        else:
            path = Path(args.config).resolve(); config = json.loads(path.read_text(encoding='utf-8'))
            if args.command == 'workflow':
                from company.workflows import run
                report = asyncio.run(run(config, path.parent, args.output, args.allow_actions, args.workers, args.repeats))
            elif args.command == 'load':
                from company.load import run
                report = asyncio.run(run(config, args.allow_load))
            else:
                from company.evidence import assess
                report = assess(config)
        save(report, args.output)
        print(('PASS' if report['passed'] else 'NOT PASSED / INCOMPLETE') + ' — ' + str(Path(args.output) / 'report.html'))
        return 0 if report['passed'] else 1
    except (ValueError, KeyError, PermissionError, ImportError, OSError) as exc:
        p.exit(2, type(exc).__name__ + ': ' + str(exc) + '\n')

if __name__ == '__main__': raise SystemExit(main())
