"""DiscoverCars: serviço existente convertido para histórico comum."""
from datetime import date, datetime
from decimal import Decimal
import hashlib
import importlib.util
from pathlib import Path
import re
from uuid import uuid4
from suiteviagem.core.models import money, new_query

ROOT = Path(__file__).resolve().parents[2]

def load_engine():
    path = ROOT/'scraper_carro/discovercars.py'
    spec = importlib.util.spec_from_file_location('suiteviagem_discovercars_engine',path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine, 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def normalize(row, query_id, engine, requested):
    if row['Moeda'] != 'BRL': raise ValueError('Moeda diferente de BRL.')
    source = engine.ler_consulta(row['Link'])
    if engine.identidade(source) != engine.identidade(requested):
        raise ValueError('Oferta de outra consulta.')
    if row['Retirada'] != source['PickupDateTime'] or row['Devolucao'] != source['DropOffDateTime']:
        raise ValueError('Datas do registro diferem do link.')
    if (row['LocalRetiradaId'],row['LocalDevolucaoId'],row['Residencia'],row['Idade']) != (source['PickupLocationId'],source['DropOffLocationId'],source['ResidenceCountry'],source['DriverAge']):
        raise ValueError('Condições do registro diferem do link.')
    cents = money(row['TotalBRL'])
    if cents <= 0: raise ValueError('Total do carro deve ser positivo.')
    coverage = {'Incluída':True,'Não incluída':False}.get(row.get('CoberturaAdicional'))
    raw = {k: str(v) if isinstance(v,Decimal) else v for k,v in row.items()}
    return {'result_id':str(uuid4()),'query_id':query_id,'kind':'car_offer',
            'title':row['Modelo'],'source_url':row['Link'],'source_id':None,
            'observed_at':row['ColetadoEm'],'location':{'name':row.get('LocalSelecionado'), 'pickup_id':row['LocalRetiradaId'],'dropoff_id':row['LocalDevolucaoId']},
            'period':{'start':row['Retirada'],'end':row['Devolucao'],'timezone':None},
            'price':{'currency':'BRL','minor_unit':2,'amount_minor':cents,'basis':'rental_total',
                     'taxes_status':'unknown','additional_taxes_minor':None,'total_minor':None,
                     'optional_coverage_included':coverage,'source_text':str(row['TotalBRL'])},
            'availability':'listed','details':{'supplier':row.get('Locadora'),'category':row.get('Categoria'),
                'rating':row.get('Nota'),'reviews':row.get('Avaliacoes'),'advertised_total_minor':cents,
                'residence_country':row['Residencia'],'driver_age':row['Idade'],'source_record':raw},
            'warnings':['Total anunciado para a locação; composição das taxas não confirmada.', 'Fuso dos horários locais não fornecido pela consulta.']}

def search(history, location, start, end, limit=5, *, engine=None, log=print):
    if not location.strip() or type(limit) is not int or not 1<=limit<=100:
        raise ValueError('Informe local e limite de 1 a 100.')
    for value in (start,end):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('Use AAAA-MM-DD.')
    if date.fromisoformat(end)<=date.fromisoformat(start):raise ValueError('Devolução precisa ser posterior à retirada.')
    query = new_query('cars',{'location':location.strip(),'start_date':start,'end_date':end,'limit':limit})
    qid=history.create(query)
    history.start(qid)
    log('Consulta registrada: '+qid)
    results,errors,warnings=[],[],[]
    effective,version,report={},None,{}
    status='succeeded'
    try:
        if engine is None:engine,version=load_engine()
        report=engine.coletar_ofertas(location,start,end,limit,log)
        effective=report['consulta']
        if date.fromisoformat(effective['PickupDateTime'][:10])!=date.fromisoformat(start) or date.fromisoformat(effective['DropOffDateTime'][:10])!=date.fromisoformat(end):
            raise ValueError('Datas efetivas diferentes das solicitadas.')
        for row in report['resultados']:
            results.append(normalize(row,qid,engine,effective))
        warnings.extend(report['erros'])
        if report.get('csv'):warnings.append('CSV do coletor: '+report['csv'])
    except KeyboardInterrupt as exc:
        report['timings']=getattr(exc,'car_timings',report.get('timings',{}))
        status='cancelled'
    except Exception as exc:
        report['timings']=getattr(exc,'car_timings',report.get('timings',{}))
        status='failed'
        errors.append({'code':'cars_error','stage':'collection_or_normalization','message':str(exc)[:2000]})
        options=getattr(exc,'location_options',None)
        if isinstance(options,list) and options and all(isinstance(x,str) for x in options):
            errors[-1].update(code='location_choice_required',message='Escolha o local de retirada para continuar.',location_options=options[:30])
    coverage={'status':'partial','scope':'Menores totais entre as ofertas coletadas com Price confirmado.',
              'metrics':[{'name':'returned','unit':'offers','value':len(results)},
                         {'name':'collected','unit':'offers','value':report.get('ofertas_coletadas')},
                         {'name':'requested_limit','unit':'offers','value':limit}],
              'stop_reason':report.get('motivo',status),
              'limitations':['Não garante todas as ofertas disponíveis; quantidade total do site não medida.']}
    for name,value in report.get('timings',{}).items():
        if isinstance(name,str) and name.endswith('_seconds') and type(value) in (int,float) and value>=0:
            coverage['metrics'].append({'name':name.removesuffix('_seconds')+'_milliseconds','unit':'milliseconds','value':round(value*1000)})
    return history.finish(qid,status=status,results=results,coverage=coverage,effective=effective,
                          errors=errors,warnings=warnings,collector_version=version)
