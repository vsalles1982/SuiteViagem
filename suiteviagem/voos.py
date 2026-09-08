import argparse
from pathlib import Path
from suiteviagem.history import History
from suiteviagem.adapters.google_flights import search

def main():
    p=argparse.ArgumentParser(description='Google Flights integrado: preços por data e histórico')
    p.add_argument('--origem',required=True);p.add_argument('--destino',required=True)
    p.add_argument('--horizonte',type=int,default=7);p.add_argument('--intervalo',type=int,default=1)
    p.add_argument('--ida-volta',action='store_true');p.add_argument('--duracao',type=int,default=7)
    p.add_argument('--rss',action='store_true',help='Atualiza o RSS desta rota usando o motor existente.')
    p.add_argument('--nome',help='Nome da rota usado no arquivo RSS.')
    p.add_argument('--db',type=Path,default=Path(__file__).resolve().parent.parent/'data/suiteviagem.sqlite3')
    a=p.parse_args()
    try:
        with History(a.db) as h:r=search(h,a.origem,a.destino,a.horizonte,a.intervalo,
           roundtrip=a.ida_volta,duration=a.duracao,rss=a.rss,name=a.nome)
    except (ValueError,OSError) as exc:p.exit(1,f'Erro: {exc}\n')
    print(f"\n✓ Histórico salvo: {r['query_id']}")
    print(f"Estado: {r['status']} | Datas com preço: {len(r['results'])} | Cobertura: {r['coverage']['status']}")
    for item in r['results']:
        cents=item['price']['amount_minor']
        print(f"{item['title']} | Menor preço coletado: R$ {cents//100},{cents%100:02d}")
    for error in r['errors']:print('Erro:',error['message'])
    for warning in r['warnings']:print('Aviso:',warning)
    if r['status']!='succeeded':raise SystemExit(130 if r['status']=='cancelled' else 1)
if __name__=='__main__':main()
