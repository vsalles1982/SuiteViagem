from pathlib import Path
from suiteviagem.history import History

if __name__ == '__main__':
    qid='71e5b01c-0c63-48ae-b435-30b16e72eea5'
    db=Path(__file__).resolve().parents[1]/'data/suiteviagem.sqlite3'
    if not db.is_file():
        raise SystemExit('Banco não encontrado; nenhum reparo realizado.')
    with History(db) as h:
        try:
            q=h.get(qid)
        except KeyError:
            q=None
        if q and q['module']=='cars' and q['status']=='running' and not q['results']:
            h.finish(qid,status='failed',results=[],coverage={'status':'unknown','scope':'Consulta interrompida na gravação das métricas da v12.','metrics':[],'stop_reason':'history_metrics_error','limitations':['Resultados e tempos finais não foram gravados.']},effective=q.get('effective',{}),errors=[{'code':'history_metrics_error','stage':'history','message':'A v12 enviou tempos decimais ao campo de contagem; a finalização foi rejeitada. Registro encerrado após correção.'}],warnings=q.get('warnings',[]),collector_version=q.get('collector_version'))
            print('✓ Consulta antiga encerrada como falha de gravação.')
        else:
            print('Nenhum registro pendente elegível para reparo.')
