"""Contrato v1: documentos JSON validados, sem dependências externas."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from uuid import UUID, uuid4

SOURCES = {'flights': 'google_flights', 'hotels': 'booking', 'cars': 'discovercars', 'events': 'shotgun'}
KINDS = {'flights': 'flight_date_quote', 'hotels': 'hotel_offer', 'cars': 'car_offer', 'events': 'event'}
BASES = {'flights': 'flight_quote', 'hotels': 'stay_total', 'cars': 'rental_total', 'events': 'ticket_lot'}
FINAL = {'succeeded', 'failed', 'cancelled', 'interrupted'}

def now():
    return datetime.now(timezone.utc).isoformat()

def check(condition, message):
    if not condition:
        raise ValueError(message)

def money(value):
    """BRL decimal → centavos. Rejeita floats e arredondamento implícito."""
    check(isinstance(value, (str, Decimal, int)) and not isinstance(value, bool), 'Use string decimal, Decimal ou inteiro para dinheiro.')
    try:
        number = Decimal(value)
        check(number.is_finite() and number >= 0, 'Preço deve ser finito e não negativo.')
        cents = number * 100
        check(cents == cents.to_integral_value(), 'BRL aceita até dois centavos decimais.')
        return int(cents)
    except InvalidOperation as exc:
        raise ValueError('Preço decimal inválido.') from exc

def stamp(value):
    check(isinstance(value, str), 'Instante obrigatório.')
    parsed = datetime.fromisoformat(value)
    check(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'Instante precisa de fuso.')
    return parsed

def identifier(value):
    UUID(value)

def new_query(module, requested, parent_query_id=None):
    check(module in SOURCES, 'Módulo desconhecido.')
    if parent_query_id is not None:
        identifier(parent_query_id)
    return {'schema_version': 1, 'query_id': str(uuid4()), 'parent_query_id': parent_query_id,
            'module': module, 'source': SOURCES[module], 'requested': requested, 'effective': {},
            'created_at': now(), 'started_at': None, 'finished_at': None, 'status': 'queued',
            'coverage': {'status': 'unknown', 'scope': 'Consulta solicitada', 'metrics': [],
                         'stop_reason': None, 'limitations': []},
            'results': [], 'errors': [], 'warnings': [], 'collector_version': None}

def validate(query):
    # Round-trip também garante que o contrato pode ser salvo/exportado como JSON.
    json.dumps(query, allow_nan=False)
    check(query['schema_version'] == 1, 'Versão de contrato não suportada.')
    identifier(query['query_id'])
    if query['parent_query_id'] is not None:
        identifier(query['parent_query_id'])
    module = query['module']
    check(module in SOURCES and query['source'] == SOURCES[module], 'Módulo/fonte incompatíveis.')
    check(isinstance(query['requested'], dict) and isinstance(query['effective'], dict), 'Parâmetros precisam ser objetos.')
    created = stamp(query['created_at'])
    status = query['status']
    check(status in FINAL | {'queued', 'running'}, 'Status inválido.')
    started = stamp(query['started_at']) if query['started_at'] else None
    finished = stamp(query['finished_at']) if query['finished_at'] else None
    check(started is None or started >= created, 'Início anterior à criação.')
    check(finished is None or finished >= (started or created), 'Fim anterior ao início.')
    check((status in FINAL) == (finished is not None), 'Estado final exige instante de término.')
    check(status != 'running' or started is not None, 'Execução exige início.')
    check(status != 'queued' or (started is None and not query['results']), 'Fila não pode conter execução/resultados.')
    coverage = query['coverage']
    check(coverage['status'] in {'unknown', 'partial', 'complete_for_scope'}, 'Cobertura inválida.')
    check(isinstance(coverage['scope'], str) and bool(coverage['scope']), 'Escopo obrigatório.')
    check(isinstance(coverage['limitations'], list), 'Limitações devem ser lista.')
    for metric in coverage['metrics']:
        check(isinstance(metric['name'], str) and isinstance(metric['unit'], str), 'Métrica exige nome e unidade.')
        check(metric['value'] is None or type(metric['value']) is int and metric['value'] >= 0, 'Contagem inválida.')
    for key in ('results', 'errors', 'warnings'):
        check(isinstance(query[key], list), f'{key} deve ser lista.')
    seen = set()
    for item in query['results']:
        identifier(item['result_id'])
        check(item['result_id'] not in seen, 'Resultado duplicado.')
        seen.add(item['result_id'])
        check(item['query_id'] == query['query_id'], 'Resultado de outra consulta.')
        check(item['kind'] == KINDS[module], 'Tipo de resultado incompatível.')
        check(isinstance(item['title'], str) and bool(item['title'].strip()), 'Título obrigatório.')
        stamp(item['observed_at'])
        check(item['availability'] in {'listed', 'available', 'sold_out', 'unknown'}, 'Disponibilidade inválida.')
        check(isinstance(item['details'], dict), 'Detalhes devem ser objeto.')
        price = item['price']
        if price is None:
            continue
        check(price['currency'] == 'BRL' and price['minor_unit'] == 2, 'MVP aceita somente BRL.')
        check(price['basis'] == BASES[module], 'Base de preço incompatível.')
        for key in ('amount_minor', 'additional_taxes_minor', 'total_minor'):
            check(price[key] is None or type(price[key]) is int and price[key] >= 0, 'Centavos devem ser inteiros não negativos.')
        check(price['optional_coverage_included'] is None or type(price['optional_coverage_included']) is bool, 'Cobertura opcional inválida.')
        tax = price['taxes_status']
        amount, extra, total = (price[k] for k in ('amount_minor', 'additional_taxes_minor', 'total_minor'))
        check(tax in {'included', 'added', 'unknown'}, 'Estado de taxas inválido.')
        if tax == 'unknown':
            check(total is None and extra is None, 'Taxas desconhecidas não confirmam total.')
        elif tax == 'included':
            check(amount is not None and extra == 0 and total == amount, 'Total com taxas incluídas inconsistente.')
        else:
            check(amount is not None and extra is not None and total == amount + extra, 'Soma de taxas inconsistente.')
    return query
