import argparse
from pathlib import Path
from suiteviagem.history import History
from suiteviagem.adapters.booking import search

def main():
    p=argparse.ArgumentParser(description='Booking integrado ao histórico — 2 adultos, 1 quarto')
    p.add_argument('--destino',required=True)
    p.add_argument('--checkin',required=True)
    p.add_argument('--checkout',required=True)
    p.add_argument('--db',type=Path,default=Path(__file__).resolve().parent.parent/'data/suiteviagem.sqlite3')
    a=p.parse_args()
    try:
        with History(a.db) as h:r=search(h,a.destino,a.checkin,a.checkout)
    except (ValueError,OSError) as exc:p.exit(1,f'Erro: {exc}\n')
    print(f"\n✓ Histórico salvo: {r['query_id']}")
    print(f"Estado: {r['status']} | Hotéis: {len(r['results'])} | Cobertura: {r['coverage']['status']}")
    for item in r['results']:
        price=item['price']
        total=price['total_minor'] if price else None
        label=f'R$ {total//100},{total%100:02d}' if total is not None else 'não confirmado'
        print(f"{item['title']} | Total com taxas exibidas: {label}")
    for e in r['errors']:print('Erro:',e['message'])
    if r['status']!='succeeded':raise SystemExit(130 if r['status']=='cancelled' else 1)
if __name__=='__main__':main()
