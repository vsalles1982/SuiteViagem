import argparse
import json
from pathlib import Path
from suiteviagem.history import History
from suiteviagem.demo import run

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description='SuiteViagem — contrato e histórico local v1')
    parser.add_argument('--db', type=Path, help='Banco explícito; demonstração usa banco separado por padrão.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('demo', help='Grava quatro consultas fictícias, sem abrir navegador.')
    listing = sub.add_parser('historico', help='Lista consultas persistidas.')
    listing.add_argument('--modulo', choices=['flights', 'hotels', 'cars', 'events'])
    show = sub.add_parser('consulta', help='Exibe JSON de uma consulta.')
    show.add_argument('id')
    backup = sub.add_parser('backup', help='Cria cópia consistente em um arquivo novo.')
    backup.add_argument('arquivo', type=Path)
    args = parser.parse_args()
    path = args.db or ROOT / 'data' / ('suiteviagem-demo.sqlite3' if args.command == 'demo' else 'suiteviagem.sqlite3')
    try:
        with History(path) as history:
            if args.command == 'demo':
                ids = run(history)
                print('✓ 4 consultas FICTÍCIAS gravadas. Nenhum fornecedor foi consultado.')
                print(f'Banco: {path}')
                for query_id in ids:
                    print(query_id)
            elif args.command == 'historico':
                rows = history.list(args.modulo)
                if not rows:
                    print('Histórico vazio.')
                for row in rows:
                    print(f"{row['query_id']} | {row['module']} | {row['status']} | {row['created_at']}")
            elif args.command == 'consulta':
                print(json.dumps(history.get(args.id), ensure_ascii=False, indent=2))
            elif args.command == 'backup':
                history.backup(args.arquivo)
                print(f'✓ Backup: {args.arquivo}')
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f'Erro: {exc}\n')

if __name__ == '__main__':
    main()
