"""Shotgun → contrato v1. Usa o motor instalado, sem alterar sua TUI."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
from pathlib import Path
import re
from urllib.parse import urlparse
from uuid import uuid4
from suiteviagem.core.models import money, new_query, now

ROOT = Path(__file__).resolve().parents[2]

def load_engine(root=ROOT):
    path = root / 'shotgun-events-scraper/shotgun_terminal_estavel.py'
    spec = importlib.util.spec_from_file_location('suiteviagem_shotgun_engine', path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine, 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()

def safe_url(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname == 'shotgun.live' and parsed.path.startswith('/en/events/')

def ticket(event, instant):
    offers = event.get('offers', [])
    if isinstance(offers, dict): offers = [offers]
    if not isinstance(offers, list): offers = []
    eligible = []
    for offer in offers:
        if not isinstance(offer, dict): continue
        status = str(offer.get('availability', '')).rstrip('/').rsplit('/', 1)[-1]
        if status not in {'InStock', 'LimitedAvailability'}: continue
        try:
            valid = True
            for key, initial in (('validFrom', True), ('validThrough', False), ('availabilityStarts', True), ('availabilityEnds', False)):
                if offer.get(key):
                    bound = datetime.fromisoformat(offer[key].replace('Z', '+00:00'))
                    if bound.tzinfo is None or (initial and instant < bound) or (not initial and instant > bound):
                        valid = False
            amount = Decimal(str(offer.get('price')))
            currency = str(offer.get('priceCurrency', '')).strip().upper()
            if valid and currency and amount.is_finite() and amount >= 0:
                eligible.append((amount, currency, offer))
        except (ValueError, TypeError, AttributeError, InvalidOperation):
            continue
    if not eligible:
        return None, None, ['Nenhum lote com preço e disponibilidade confirmáveis.']
    if {entry[1] for entry in eligible} != {'BRL'}:
        return None, None, ['Moeda não suportada ou ofertas em moedas diferentes; preço preservado nos dados de origem.']
    amount, _, selected = min(eligible, key=lambda entry: entry[0])
    try:
        cents = money(amount)
    except ValueError:
        return None, None, ['Preço com precisão incompatível com BRL.']
    price = {'currency': 'BRL', 'minor_unit': 2, 'amount_minor': cents, 'basis': 'ticket_lot',
             'taxes_status': 'unknown', 'additional_taxes_minor': None, 'total_minor': None,
             'optional_coverage_included': None, 'source_text': str(selected.get('price'))}
    return price, selected, ['Taxas finais e quantidade de pessoas por ingresso não confirmadas.']

def normalize(event, query_id, engine, observed_at=None):
    observed_at = observed_at or now()
    raw_start = datetime.fromisoformat(event['startDate'].replace('Z', '+00:00'))
    if raw_start.tzinfo is None:
        raise ValueError('Início do evento sem fuso explícito.')
    start = engine.obter_inicio_local(event)
    end = None
    if event.get('endDate'):
        end = datetime.fromisoformat(event['endDate'].replace('Z', '+00:00'))
        if end.tzinfo is None or end < start:
            raise ValueError('Fim do evento inválido ou sem fuso.')
        end = end.astimezone(start.tzinfo)
    price, selected, warnings = ticket(event, datetime.fromisoformat(observed_at))
    url = event.get('url')
    if not isinstance(url, str) or not safe_url(url):
        url = None
        warnings.append('Link do evento ausente ou não reconhecido.')
    return {'result_id': str(uuid4()), 'query_id': query_id, 'kind': 'event',
            'title': event.get('name') or 'Evento sem nome', 'source_url': url, 'source_id': event.get('@id'),
            'observed_at': observed_at, 'location': {'address': engine.obter_local(event)},
            'period': {'start': start.isoformat(), 'end': end.isoformat() if end else None, 'timezone': getattr(start.tzinfo, 'key', None)},
            'price': price, 'availability': 'available' if selected else 'unknown',
            'details': {'organizer': engine.obter_organizador(event), 'lineup': engine.resumir_lineup(event),
                        'ticket': selected, 'source_event': event}, 'warnings': warnings}

def search(history, city, start, end, limit=5, *, engine=None, log=print):
    city = city.strip()
    if not city or not 1 <= limit <= 50:
        raise ValueError('Informe cidade e limite de 1 a 50.')
    for value in (start, end):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value): raise ValueError('Use datas AAAA-MM-DD.')
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first: raise ValueError('Data final anterior à inicial.')
    query = new_query('events', {'city': city, 'start_date': start, 'end_date': end, 'limit': limit})
    query_id = history.create(query)
    history.start(query_id)
    log(f'Consulta registrada: {query_id}')
    results, errors, summary = [], [], {}
    effective, version = {}, None
    status = 'succeeded'
    phase = 'load_engine'
    linked = analyzed = outside = missing = 0
    stop = 'unknown'
    try:
        if engine is None: engine, version = load_engine()
        phase = 'city'
        slug = engine.criar_slug(city)
        if not re.fullmatch(r'[a-z0-9-]+', slug): raise ValueError('Cidade inválida.')
        url = f'https://shotgun.live/en/cities/{slug}'
        log(f'Consultando agenda: {url}')
        if not engine.pagina_da_cidade_valida(engine.baixar_pagina(url)):
            raise ValueError('Página da cidade não reconhecida pelo motor.')
        effective = {'city_slug': slug, 'city_url': url, 'start_date': start, 'end_date': end, 'limit': limit,
                     'date_rule': 'event_local_start_inclusive'}
        phase = 'agenda'
        links = list(dict.fromkeys(engine.coletar_links(url, summary)))
        linked = len(links)
        errors.extend({'code': 'agenda_error', 'stage': phase, 'message': item['erro'], 'url': item['url']} for item in summary.get('falhas_agenda', []))
        phase = 'events'
        for link in links:
            if len(results) >= limit: break
            analyzed += 1
            log(f'Analisando {analyzed}/{linked}; eventos no período: {len(results)}/{limit}')
            try:
                if not safe_url(link): raise ValueError('Link da agenda fora do domínio/caminho esperado.')
                page = engine.baixar_pagina(link)
                event = engine.localizar_music_event(page)
                if not event or not event.get('startDate'):
                    missing += 1
                    continue
                event = dict(event)
                event['url'] = event.get('url') or link
                item = normalize(event, query_id, engine)
                if first <= datetime.fromisoformat(item['period']['start']).date() <= last:
                    results.append(item)
                else: outside += 1
            except Exception as exc:
                errors.append({'code': 'event_error', 'stage': phase, 'message': str(exc), 'url': link})
            finally:
                engine.time.sleep(0.6)
        stop = 'result_limit' if len(results) >= limit else summary.get('fim_agenda', 'links_processed')
        if errors: status = 'failed'
    except KeyboardInterrupt:
        status, stop = 'cancelled', 'user_cancelled'
    except Exception as exc:
        status, stop = 'failed', 'error'
        errors.append({'code': 'collector_error', 'stage': phase, 'message': str(exc)})
    results.sort(key=lambda item: item['period']['start'])
    metrics = [{'name': name, 'unit': unit, 'value': value} for name, unit, value in (
        ('found', 'links', linked), ('analyzed', 'links', analyzed), ('not_analyzed', 'links', linked-analyzed),
        ('outside_period', 'events', outside), ('missing_data', 'links', missing), ('returned', 'events', len(results)),
        ('pages_read', 'pages', summary.get('paginas_lidas')))]
    coverage = {'status': 'partial' if errors or missing or analyzed < linked or len(results) >= limit or summary.get('fim_agenda') != 'página sem novos links' else 'complete_for_scope',
                'scope': 'Links encontrados na agenda; eventos com início local no período solicitado.',
                'metrics': metrics, 'stop_reason': stop,
                'limitations': ['Não representa todos os eventos da cidade nem um ranking dos mais baratos.',
                                f'Encerramento da agenda: {summary.get("fim_agenda", "não concluída")}']}
    if status in {'cancelled', 'failed'}: coverage['status'] = 'partial'
    return history.finish(query_id, status=status, results=results, coverage=coverage, effective=effective,
                          errors=errors, collector_version=version)
