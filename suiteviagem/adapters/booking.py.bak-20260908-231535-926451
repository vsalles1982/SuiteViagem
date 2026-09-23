"""Booking: registros do motor → contrato comum, mantendo Excel e GUI."""
from datetime import date
import hashlib
import importlib.util
from pathlib import Path
import re
from uuid import uuid4
from suiteviagem.core.models import money, new_query

ROOT=Path(__file__).resolve().parents[2]

def load_engine():
    path=ROOT/'booking-hotel-scraper/hotels_booking.py'
    spec=importlib.util.spec_from_file_location('suiteviagem_booking_engine',path)
    engine=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine,'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def nullable(value):
    return None if value in ('Não informado','Não informada','',None) else value

def price_from_text(row):
    raw=row.get('Price Text','')
    match=re.fullmatch(r'\s*(?:R\$|BRL)\s*([0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2})?)\s*',raw)
    if row.get('Currency')!='BRL' or not match:return None
    amount=money(match[1].replace('.','').replace(',','.'))
    if amount<=0:return None
    taxes=row.get('Taxes Text','')
    status,extra,total='unknown',None,None
    if re.fullmatch(r'\s*Impostos e taxas incluídos\s*',taxes,re.I):
        status,extra,total='included',0,amount
    else:
        match=re.fullmatch(r'\s*\+\s*R\$\s*([0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2})?)\s+em impostos e taxas\s*',taxes,re.I)
        if match:
            extra=money(match[1].replace('.','').replace(',','.'))
            status,total='added',amount+extra
    return {'currency':'BRL','minor_unit':2,'amount_minor':amount,'basis':'stay_total',
            'taxes_status':status,'additional_taxes_minor':extra,'total_minor':total,
            'optional_coverage_included':None,'source_text':raw}

def normalize(row,qid,start,end):
    if row['Check-in']!=start or row['Check-out']!=end:
        raise ValueError('Datas do registro diferem da consulta.')
    if (row['Adults'],row['Children'],row['Rooms'])!=(2,0,1):
        raise ValueError('Ocupação inesperada no registro.')
    warnings=['Condições enviadas pelo coletor; confirmação independente da seleção no site ainda não implementada.']
    if row.get('Details Error'):warnings.append(row['Details Error'])
    stars=nullable(row.get('Stars'))
    if type(stars) is not int or not 1<=stars<=5:stars=None
    price=price_from_text(row)
    if price is None:warnings.append('Preço em BRL não confirmado; hospedagem preservada.')
    elif price['total_minor'] is None:warnings.append('Total com taxas não confirmado.')
    return {'result_id':str(uuid4()),'query_id':qid,'kind':'hotel_offer',
            'title':nullable(row.get('Hotel Name')) or 'Hospedagem sem nome','source_url':nullable(row.get('Hotel URL')),'source_id':None,
            'observed_at':row['Collected At'],
            'location':{'name':row.get('Destination'),'address':nullable(row.get('Address')),'latitude':row.get('Latitude'),'longitude':row.get('Longitude')},
            'period':{'start':start,'end':end,'timezone':None},'price':price,'availability':'listed',
            'details':{'stars':stars,'review_score':row.get('Review Score (/10)'),
                       'room':nullable(row.get('Room Text')),'stay_text':nullable(row.get('Stay Text')),
                       'adults':2,'children':0,'rooms':1,'nights':row['Nights'],
                       'details_status':row.get('Details Status'),'source_record':row},'warnings':warnings}

def search(history,destination,start,end,*,engine=None,log=print):
    if not destination.strip():raise ValueError('Informe destino.')
    for value in (start,end):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('Use AAAA-MM-DD.')
    if date.fromisoformat(end)<=date.fromisoformat(start):raise ValueError('Check-out deve ser posterior ao check-in.')
    requested={'destination':destination.strip(),'checkin':start,'checkout':end,'adults':2,'children':0,'rooms':1,'currency':'BRL'}
    q=new_query('hotels',requested)
    qid=history.create(q);history.start(qid)
    log('Consulta registrada: '+qid)
    results,errors,warnings=[],[],[]
    report,version={},None
    status='succeeded'
    try:
        if engine is None:engine,version=load_engine()
        report=engine.run_scraping(destination,start,end,return_records=True)
        for row in report['records']:
            try:results.append(normalize(row,qid,start,end))
            except Exception as exc:
                errors.append({'code':'hotel_normalization','message':str(exc),'hotel':row.get('Hotel Name')})
        if errors:status='failed'
        if report.get('excel'):warnings.append('Excel do coletor: '+report['excel'])
    except KeyboardInterrupt:status='cancelled'
    except Exception as exc:
        status='failed';errors.append({'code':'booking_error','message':str(exc)[:2000]})
    results.sort(key=lambda item:(item['price'] is None or item['price']['total_minor'] is None,
                                item['price']['total_minor'] if item['price'] and item['price']['total_minor'] is not None else 0))
    coverage={'status':'partial','scope':'Cartões carregados pelo motor Booking; parada por ausência de novos cartões.',
              'metrics':[{'name':'returned','unit':'hotels','value':len(results)},
                         {'name':'extracted','unit':'hotels','value':len(report['records']) if 'records' in report else None}],
              'stop_reason':'collector_finished' if status=='succeeded' else status,
              'limitations':['Não garante todas as hospedagens disponíveis.', 'Parâmetros do site não confirmados independentemente pelo adaptador.']}
    return history.finish(qid,status=status,results=results,coverage=coverage,
                          effective={'search_url':report.get('search_url'),'confirmed_parameters':None},
                          errors=errors,warnings=warnings,collector_version=version)
