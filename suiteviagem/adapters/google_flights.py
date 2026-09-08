"""Menores preços por data do motor Google Flights no histórico comum."""
from datetime import date, timedelta
import hashlib
import importlib.util
from pathlib import Path
import re
from uuid import uuid4
from suiteviagem.core.models import money, new_query, now

ROOT=Path(__file__).resolve().parents[2]

def load_engine():
    path=ROOT/'passagens/google-flights/gerar_feeds_voos.py'
    spec=importlib.util.spec_from_file_location('suiteviagem_google_flights_engine',path)
    engine=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine,'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def normalize(item,qid,engine,origin,destination,roundtrip,duration,observed_at):
    departure=date.fromisoformat(item['data'])
    arrival=departure+timedelta(days=duration) if roundtrip else None
    # O motor antigo retorna int/float; repr decimal evita arredondamento adicional.
    value=item['preco']
    if type(value) not in (int,float):raise ValueError('Preço do motor não é numérico.')
    cents=money(str(value))
    if cents<=0:raise ValueError('Preço deve ser positivo.')
    return {'result_id':str(uuid4()),'query_id':qid,'kind':'flight_date_quote',
            'title':f'{origin} → {destination} | {departure.isoformat()}',
            'source_url':engine.montar_url(origin,destination,item['data'],roundtrip,duration),
            'source_id':None,'observed_at':observed_at,'location':{'origin':origin,'destination':destination},
            'period':{'start':departure.isoformat(),'end':arrival.isoformat() if arrival else None,'timezone':None},
            'price':{'currency':'BRL','minor_unit':2,'amount_minor':cents,'basis':'flight_quote',
                     'taxes_status':'unknown','additional_taxes_minor':None,'total_minor':None,
                     'optional_coverage_included':None,'source_text':str(value)},
            'availability':'listed','details':{'roundtrip':roundtrip,'duration_days':duration if roundtrip else None,
                'source_record':item,'observation_time_basis':'collector_return','airline':None,'flight_number':None,
                'passengers':None,'cabin':None},
            'warnings':['Menor preço entre cartões reconhecidos nesta data; não identifica um itinerário específico.',
                        'Composição das taxas não confirmada. Instante registrado ao retornar a coleta.']}

def search(history,origin,destination,horizon=7,step=1,*,roundtrip=False,duration=7,rss=False,name=None,engine=None,log=print):
    origin,destination=origin.strip().upper(),destination.strip().upper()
    if not all(re.fullmatch('[A-Z]{3}',v) for v in (origin,destination)) or origin==destination:
        raise ValueError('Informe códigos distintos de três letras, como RIO e SAO.')
    if type(horizon) is not int or not 5<=horizon<=365 or type(step) is not int or not 1<=step<=365:
        raise ValueError('Horizonte: 5 a 365 dias; intervalo: 1 a 365 dias.')
    if type(duration) is not int or not 1<=duration<=365:raise ValueError('Duração: 1 a 365 dias.')
    if type(roundtrip) is not bool or type(rss) is not bool:raise ValueError('Opções booleanas inválidas.')
    label=name or f'{origin} x {destination}'
    query=new_query('flights',{'origin':origin,'destination':destination,'horizon_days':horizon,
        'step_days':step,'start_offset_days':5,'roundtrip':roundtrip,'duration_days':duration if roundtrip else None,
        'rss_requested':rss,'route_name':label,'currency':'BRL'})
    qid=history.create(query);history.start(qid)
    log('Consulta registrada: '+qid)
    results,errors,warnings=[],[],[]
    report,version,effective={},None,{}
    status='succeeded'
    rss_error=False
    try:
        if engine is None:engine,version=load_engine()
        log('Busca começa daqui a 5 dias; o horizonte e o intervalo definem as datas amostradas.')
        report=engine.raspar_melhor_preco(label,origin,destination,horizon,step,roundtrip,duration)
        planned=report['datas']
        if not planned or len(planned)!=len(set(planned)):raise ValueError('Datas planejadas ausentes ou duplicadas.')
        for value in planned:date.fromisoformat(value)
        effective={'planned_dates':planned,'parameters_sent':{'origin':origin,'destination':destination,
                   'roundtrip':roundtrip,'duration_days':duration if roundtrip else None},'confirmed_parameters':None}
        seen=set()
        observed=now()
        for item in report['sucessos']:
            if item['data'] not in planned or item['data'] in seen:raise ValueError('Data de resultado inesperada ou duplicada.')
            seen.add(item['data'])
            results.append(normalize(item,qid,engine,origin,destination,roundtrip,duration,observed))
        for failure in report['falhas']:
            errors.append({'code':'date_failed','stage':'collection','message':failure.get('erro','Falha na data'),
                           'date':failure.get('data'),'attempts':failure.get('tentativas',[])})
        missing=set(planned)-seen-{f.get('data') for f in report['falhas']}
        if missing:errors.append({'code':'missing_dates','stage':'collection','message':'Datas sem resposta: '+', '.join(sorted(missing))})
        if errors or not results:status='failed'
        if rss and results:
            # RSS usa a mesma lista validada de sucessos e o menor valor.
            cheapest=min(report['sucessos'],key=lambda item:item['preco'])
            feed_report=dict(report,preco=cheapest['preco'],data=cheapest['data'],
                             url=engine.montar_url(origin,destination,cheapest['data'],roundtrip,duration))
            try:
                path=engine.criar_rss_local(label,origin,destination,feed_report,
                      f'{horizon} dias, intervalo {step}',roundtrip,f'{duration} dias' if roundtrip else None)
                warnings.append('RSS atualizado: '+str(path));log(warnings[-1])
            except Exception as exc:
                rss_error=True
                warnings.append('Falha ao exportar RSS; resultados da coleta preservados: '+str(exc))
        elif rss:
            warnings.append('Nenhum preço confirmado; RSS anterior preservado.')
    except KeyboardInterrupt:status='cancelled'
    except Exception as exc:
        status='failed';errors.append({'code':'flights_error','stage':'collection_or_normalization','message':str(exc)[:2000]})
    results.sort(key=lambda item:(item['price']['amount_minor'],item['period']['start']))
    planned=report.get('datas')
    coverage={'status':'complete_for_scope' if status=='succeeded' else 'partial',
        'scope':'Datas amostradas pelo motor; cartões reconhecidos na aba Menores preços.',
        'metrics':[{'name':'planned','unit':'dates','value':len(planned) if planned is not None else None},
                   {'name':'with_price','unit':'dates','value':len(results)},
                   {'name':'failed','unit':'dates','value':len(report['falhas']) if 'falhas' in report else None}],
        'stop_reason':status,'limitations':['Não representa todas as datas ou todas as ofertas.',
                    'Rota, passageiros e classe não são confirmados independentemente pelo adaptador.']}
    if rss_error:warnings.append('É possível consultar o histórico mesmo com falha de RSS.')
    return history.finish(qid,status=status,results=results,coverage=coverage,effective=effective,
                          errors=errors,warnings=warnings,collector_version=version)
