"""Dados fictícios para validar a base; não consulta fornecedores."""
from uuid import uuid4
from suiteviagem.core.models import BASES, KINDS, SOURCES, new_query, now

def run(history):
    ids = []
    for module in SOURCES:
        query = new_query(module, {'demo': True, 'destination': 'Destino de demonstração'})
        query_id = history.create(query)
        history.start(query_id)
        price = {'currency': 'BRL', 'minor_unit': 2, 'amount_minor': 12345, 'basis': BASES[module],
                 'taxes_status': 'unknown', 'additional_taxes_minor': None, 'total_minor': None,
                 'optional_coverage_included': None, 'source_text': 'Exemplo fictício: R$ 123,45'}
        item = {'result_id': str(uuid4()), 'query_id': query_id, 'kind': KINDS[module],
                'title': f'DEMONSTRAÇÃO — {module}', 'source_url': None, 'source_id': None,
                'observed_at': now(), 'location': None, 'period': None, 'price': price,
                'availability': 'unknown', 'details': {'demo': True}, 'warnings': ['Dado fictício; não é uma oferta.']}
        coverage = {'status': 'partial', 'scope': 'Exemplo local', 'metrics': [{'name': 'returned', 'unit': 'results', 'value': 1}],
                    'stop_reason': 'demo_limit', 'limitations': ['Não houve consulta ao fornecedor.']}
        history.finish(query_id, status='succeeded', results=[item], coverage=coverage, warnings=['DEMONSTRAÇÃO'])
        ids.append(query_id)
    return ids
