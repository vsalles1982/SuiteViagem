import argparse
import json
from pathlib import Path
from suiteviagem.adapters.discovercars import search
from suiteviagem.history import History

def main():
    p=argparse.ArgumentParser(description='DiscoverCars integrado ao histórico')
    p.add_argument('--progressivo',action='store_true')
    p.add_argument('--local',required=True)
    p.add_argument('--retirada',required=True)
    p.add_argument('--devolucao',required=True)
    p.add_argument('--limite',type=int,default=5)
    p.add_argument('--db',type=Path,default=Path(__file__).resolve().parent.parent/'data/suiteviagem.sqlite3')
    args=p.parse_args()
    try:
        with History(args.db) as h:
            result=search(h,args.local,args.retirada,args.devolucao,args.limite,on_progress=(lambda q:print('SUITE_PREVIEW:'+json.dumps(q,ensure_ascii=False,separators=(',',':')),flush=True)) if args.progressivo else None)
    except (ValueError,OSError) as exc:p.exit(1,f'Erro: {exc}\n')
    print(f"\n✓ Histórico salvo: {result['query_id']}")
    print(f"Estado: {result['status']} | Carros: {len(result['results'])} | Cobertura: {result['coverage']['status']}")
    for item in result['results']:
        cents=item['price']['amount_minor']
        print(f"{item['title']} | {item['details']['supplier']} | Total anunciado: R$ {cents//100},{cents%100:02d}")
    for error in result['errors']:print('Erro:',error['message'])
    if result['status']!='succeeded':raise SystemExit(130 if result['status']=='cancelled' else 1)
if __name__=='__main__':main()
