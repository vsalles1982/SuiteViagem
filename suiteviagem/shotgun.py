"""python -m suiteviagem.shotgun --cidade 'São Paulo' --inicio ... --fim ..."""
import argparse
from pathlib import Path
from suiteviagem.adapters.shotgun import search
from suiteviagem.history import History

def main():
    parser = argparse.ArgumentParser(description='Shotgun integrado ao histórico da SuiteViagem')
    parser.add_argument('--cidade', required=True)
    parser.add_argument('--inicio', required=True)
    parser.add_argument('--fim', required=True)
    parser.add_argument('--limite', type=int, default=5)
    parser.add_argument('--db', type=Path, default=Path(__file__).resolve().parent.parent/'data/suiteviagem.sqlite3')
    args = parser.parse_args()
    try:
        with History(args.db) as history:
            result = search(history, args.cidade, args.inicio, args.fim, args.limite)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Erro: {exc}\n')
    print(f"\n✓ Histórico salvo: {result['query_id']}")
    print(f"Estado: {result['status']} | Eventos: {len(result['results'])} | Cobertura: {result['coverage']['status']}")
    for item in result['results']:
        cents = item['price']['amount_minor'] if item['price'] else None
        price = f'R$ {cents//100},{cents%100:02d}' if cents is not None else 'Não informado'
        print(f"{item['period']['start']} | {item['title']} | Lote a partir de {price}")
    for error in result['errors']: print('Aviso:', error['message'])
    print('Taxas finais não confirmadas. Resultados limitados aos links analisados.')
    if result['status'] != 'succeeded': raise SystemExit(130 if result['status'] == 'cancelled' else 1)

if __name__ == '__main__': main()
