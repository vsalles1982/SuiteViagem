"""DiscoverCars: consulta por URL, datas conferidas e totais em BRL.
Busca por local e calendário: 11h, Brasil, idade 35 e mesmo ponto.
Também aceita o link /search/ para consultas previamente configuradas.
"""
import base64
import csv
import json
import math
import re
import shutil
import time
import urllib.request
import urllib.error
from datetime import datetime
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urljoin, urlencode

from textual.app import App, ComposeResult
from textual.widgets import Header, Input, Button, Label, Log
from textual.containers import Container
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


def ler_consulta(url):
    u = urlparse(url)
    if u.scheme != 'https' or u.hostname not in ('www.discovercars.com', 'discovercars.com'):
        raise ValueError('Use um link HTTPS do DiscoverCars.')
    if not re.search(r'/(search|offer)/', u.path):
        raise ValueError('Link sem pesquisa ou oferta.')
    try:
        raw = parse_qs(u.query)['sq'][0]
        data = json.loads(base64.b64decode(raw + '=' * (-len(raw) % 4), validate=True))
        for key in ('PickupLocationId', 'DropOffLocationId', 'ResidenceCountry', 'DriverAge'):
            if not data.get(key):
                raise ValueError(key)
        a = datetime.fromisoformat(data['PickupDateTime'])
        b = datetime.fromisoformat(data['DropOffDateTime'])
        if b <= a:
            raise ValueError('período inválido')
    except Exception as exc:
        raise ValueError('Não foi possível confirmar os parâmetros sq do link.') from exc
    return data


def identidade(data):
    return tuple(data[k] for k in ('PickupLocationId', 'DropOffLocationId',
        'PickupDateTime', 'DropOffDateTime', 'ResidenceCountry', 'DriverAge'))


def converter_preco(texto):
    # BRL obrigatório; jamais relabelar euro/dólar como real.
    s = texto.replace('\xa0', ' ').strip()
    if not re.fullmatch(r'R\$\s*\d[\d.,]*', s):
        raise ValueError('Preço total sem BRL explícito: ' + s)
    s = s.replace('R$', '').strip()
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.') if s.rfind(',') > s.rfind('.') else s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '') if re.fullmatch(r'\d{1,3}(,\d{3})+', s) else s.replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(\.\d{3})+', s):
        s = s.replace('.', '')
    if not re.fullmatch(r'\d+(\.\d{1,2})?', s):
        raise ValueError('Formato de preço ambíguo')
    value = Decimal(s)
    if value <= 0:
        raise ValueError('Preço não positivo')
    return value


def formatar_preco(value):
    return ('R$ ' + f'{value:,.2f}').replace(',', 'X').replace('.', ',').replace('X', '.')


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children, self.parts = tag, dict(attrs), [], []
    def all(self):
        yield self
        for c in self.children:
            yield from c.all()
    def select(self, cls):
        return [n for n in self.all() if cls in n.attrs.get('class', '').split()]
    def text(self):
        return ' '.join(''.join(self.parts).split())


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].children.append(n)
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            self.stack.append(n)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break
    def handle_data(self, data):
        for n in self.stack:
            n.parts.append(data)


def extrair_card(card, consulta, url):
    def first(cls):
        return next((n.text() for n in card.select(cls) if n.text()), 'Não informado')
    modelo = first('CarTitle-Name')
    if modelo == 'Não informado':
        raise ValueError('Modelo ausente')
    prices = {converter_preco(n.text()) for n in card.select('SearchCar-Price')}
    if len(prices) != 1:
        raise ValueError('Total ausente ou divergente entre versões do cartão')
    total = prices.pop()
    periodo = first('SearchCar-TotalForDays')
    m = re.fullmatch(r'Total for (\d+) days?', periodo)
    dias = math.ceil((datetime.fromisoformat(consulta['DropOffDateTime']) - datetime.fromisoformat(consulta['PickupDateTime'])).total_seconds()/86400)
    if not m or int(m[1]) != dias:
        raise ValueError('Período do cartão não confirmado: ' + periodo)
    link = next((urljoin(url,n.attrs['href']) for n in card.all()
                 if n.tag == 'a' and '/offer/' in n.attrs.get('href','')), '')
    if not link or identidade(ler_consulta(link)) != identidade(consulta):
        raise ValueError('Oferta sem link com os mesmos parâmetros da consulta')
    supplier = next((n.attrs['alt'] for p in card.select('SupplierInfo-SupplierInfoWrapper')
                     for n in p.all() if n.tag == 'img' and n.attrs.get('alt')), 'Não informado')
    return dict(Modelo=modelo, Categoria=first('CarTitle-Similar'), Locadora=supplier,
        TotalBRL=total, Moeda='BRL', Periodo=periodo,
        Nota=first('SupplierInfo-RatingScore'), Avaliacoes=first('SupplierInfo-SupplierReviews'),
        Link=link, Retirada=consulta['PickupDateTime'], Devolucao=consulta['DropOffDateTime'],
        LocalRetiradaId=consulta['PickupLocationId'], LocalDevolucaoId=consulta['DropOffLocationId'],
        Residencia=consulta['ResidenceCountry'], Idade=consulta['DriverAge'])


CREATE_SEARCH_URL = 'https://www.discovercars.com/api/v2/search/create-search?'
AUTOCOMPLETE_URL = 'https://www.discovercars.com/api/v2/autocomplete'
LOCATION_CACHE = Path(__file__).resolve().parents[1] / 'data' / 'discovercars_locations.json'


def _json_request(url, *, payload=None, timeout=20):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.discovercars.com/',
    }
    data = None
    method = 'GET'
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        method = 'POST'
        headers.update({
            'Content-Type': 'application/json',
            'Origin': 'https://www.discovercars.com',
        })
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f'DiscoverCars API respondeu HTTP {response.status}')
        return json.loads(response.read().decode('utf-8'))


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _keymap(row):
    return {re.sub(r'[^a-z0-9]', '', str(k).lower()): v for k, v in row.items()}


def _first_value(row, *keys):
    km = _keymap(row)
    for key in keys:
        value = km.get(re.sub(r'[^a-z0-9]', '', key.lower()))
        if value not in (None, ''):
            return value
    return None


def _as_int(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _candidate_from_dict(row):
    """Aceita variações de schema do autocomplete; retorna apenas candidatos completos."""
    location_id = _as_int(_first_value(row, 'location_id', 'locationId', 'pickup_id', 'pickupId'))
    city_id = _as_int(_first_value(row, 'city_id', 'cityId'))
    country_id = _as_int(_first_value(row, 'country_id', 'countryId'))

    # Alguns schemas aninham cidade/país.
    city = row.get('city') if isinstance(row.get('city'), dict) else {}
    country = row.get('country') if isinstance(row.get('country'), dict) else {}
    city_id = city_id or _as_int(_first_value(city, 'id', 'city_id', 'cityId'))
    country_id = country_id or _as_int(_first_value(country, 'id', 'country_id', 'countryId'))

    if not (location_id and city_id and country_id):
        return None

    labels = []
    for key in ('label', 'name', 'title', 'description', 'full_name', 'fullName', 'location_name', 'locationName'):
        value = _first_value(row, key)
        if isinstance(value, str) and value.strip():
            labels.append(value.strip())
    for nested in (city, country):
        value = _first_value(nested, 'name', 'label', 'title')
        if isinstance(value, str) and value.strip():
            labels.append(value.strip())
    label = ', '.join(dict.fromkeys(labels)) or str(location_id)
    return {'label': label, 'location_id': location_id, 'city_id': city_id, 'country_id': country_id}


def _load_location_cache():
    try:
        raw = json.loads(LOCATION_CACHE.read_text(encoding='utf-8'))
        return raw if isinstance(raw, list) else []
    except (OSError, ValueError, TypeError):
        return []


def resolver_local_api(destino, timeout=20):
    """Resolve IDs sem navegador. Falha fechada para permitir fallback v12.1."""
    alvo = normalizar_local(destino)
    cache = _load_location_cache()
    cached = [x for x in cache if isinstance(x, dict) and normalizar_local(x.get('label', '')) == alvo]
    if len(cached) == 1:
        item = cached[0]
        if all(_as_int(item.get(k)) for k in ('location_id', 'city_id', 'country_id')):
            return item

    query = urlencode({'location': texto_busca_local(destino)})
    data = _json_request(AUTOCOMPLETE_URL + '?' + query, timeout=timeout)
    candidates = []
    seen = set()
    for row in _walk_dicts(data):
        item = _candidate_from_dict(row)
        if not item:
            continue
        key = (item['location_id'], item['city_id'], item['country_id'])
        if key not in seen:
            candidates.append(item)
            seen.add(key)

    exact = [x for x in candidates if normalizar_local(x['label']) == alvo]
    if not exact:
        # Rótulos do endpoint podem conter detalhes extras; aceitar somente match único forte.
        exact = [x for x in candidates if alvo in normalizar_local(x['label']) or normalizar_local(x['label']) in alvo]
    if len(exact) != 1:
        raise LocalAmbiguo(x['label'] for x in candidates) if candidates else ValueError('Autocomplete API não resolveu o local.')
    return exact[0]


def criar_busca_direta(destino, retirada, devolucao, log=print):
    local = resolver_local_api(destino)
    payload = {
        'is_drop_off': False,
        'pick_up_country_id': local['country_id'],
        'pick_up_city_id': local['city_id'],
        'pick_up_location_id': local['location_id'],
        'pickup_id': local['location_id'],
        'drop_off_country_id': local['country_id'],
        'drop_off_city_id': local['city_id'],
        'drop_off_location_id': local['location_id'],
        'dropoff_id': local['location_id'],
        'pickup_from': retirada.isoformat() + ' 11:00',
        'pickup_to': devolucao.isoformat() + ' 11:00',
        'pick_time': '11:00',
        'drop_time': '11:00',
        'driver_age': '35',
        'residence_country': 'BR',
        'partnerID': 0,
        'excludeLocations': 0,
        'recent_search': 0,
        'isWhitelabel': False,
    }
    body = _json_request(CREATE_SEARCH_URL, payload=payload, timeout=30)
    data = body.get('data') if isinstance(body, dict) else None
    url = data.get('url') if isinstance(data, dict) else None
    if not isinstance(url, str) or '/search/' not in urlparse(url).path:
        raise ValueError('create-search não devolveu URL canônica válida.')
    consulta = ler_consulta(url)
    esperado_r = retirada.isoformat() + 'T11:00:00'
    esperado_d = devolucao.isoformat() + 'T11:00:00'
    if (consulta['PickupLocationId'] != local['location_id'] or
            consulta['DropOffLocationId'] != local['location_id'] or
            consulta['PickupDateTime'] != esperado_r or consulta['DropOffDateTime'] != esperado_d or
            consulta['ResidenceCountry'] != 'BR' or consulta['DriverAge'] != 35):
        raise ValueError('create-search devolveu parâmetros diferentes dos solicitados.')
    log('Caminho rápido: create-search direto confirmado para ' + local['label'])
    return url, consulta, local['label']


def snapshot_cards(driver):
    """Leitura atômica do DOM para estabilidade, sem WebElement sujeito a stale."""
    return driver.execute_script("""
        return Array.from(document.querySelectorAll('.SearchList-Card')).map((el) => {
            const link = el.querySelector('a[href*="/offer/"]');
            const prices = Array.from(el.querySelectorAll('.SearchCar-Price')).map(x => (x.innerText || '').trim());
            return [(link && link.href) || '', prices.join('|'), (el.innerText || '').length];
        });
    """)


def normalizar_local(texto):
    import unicodedata
    return ' '.join(unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode().lower().split())


class LocalAmbiguo(ValueError):
    def __init__(self, options):
        self.location_options = list(dict.fromkeys(options))[:30]
        super().__init__('Escolha o local de retirada: ' + ' | '.join(self.location_options))


def escolher_rotulo(destino, opcoes):
    """Exigir correspondência única; 'Ibiza' não vira aeroporto implicitamente."""
    alvo = normalizar_local(destino)
    exatos = [rotulo for rotulo, lugar in opcoes
              if alvo in (normalizar_local(rotulo), normalizar_local(lugar))]
    if not exatos:
        exatos = [rotulo for rotulo, lugar in opcoes
                  if normalizar_local(re.sub(r'\s*\([A-Z]{3}\)\s*$', '', lugar)) == alvo]
    unicos = list(dict.fromkeys(exatos))
    if len(unicos) != 1:
        raise LocalAmbiguo(rotulo for rotulo, _ in opcoes)
    return unicos[0]


def texto_busca_local(destino):
    # O rótulo completo continua obrigatório na escolha; só a digitação é curta.
    prefixo = destino.split(',')[0].strip()
    return prefixo if 'airport' in normalizar_local(prefixo) else destino


def fase_calendario(visiveis, placeholder):
    calendarios = visiveis('.rdrCalendarWrapper')
    if not calendarios:
        return False
    compacto = any(c.find_elements(By.CSS_SELECTOR, '.rdrDateDisplayItem') for c in calendarios)
    for calendario in calendarios:
        if calendario.find_elements(By.CSS_SELECTOR,
                '.rdrDateDisplayItemActive input[placeholder="' + placeholder + '"]'):
            return True
    if compacto:
        return False
    # Desktop não possui rdrDateDisplay: a classe ativa está no campo externo.
    campos = visiveis('.DatePicker-CalendarField')
    if len(campos) != 2:
        return False
    ativos = [i for i,c in enumerate(campos)
              if 'DatePicker-CalendarField_isActive' in (c.get_attribute('class') or '').split()]
    return ativos == ([0] if placeholder == 'Early' else [1])


def abrir_busca_por_local(driver, destino, retirada, devolucao, log, tempos=None):
    from selenium.webdriver.common.keys import Keys
    wait = WebDriverWait(driver, 30)

    def visiveis(css):
        resultado = []
        for e in driver.find_elements(By.CSS_SELECTOR, css):
            if not e.is_displayed():
                continue
            ativo = driver.execute_script("""
                let node = arguments[0];
                while (node) {
                    if (node.classList && node.classList.contains('Modal-Container') &&
                        !node.classList.contains('Modal-Container_isActive')) return false;
                    if (node.getAttribute && node.getAttribute('aria-hidden') === 'true') return false;
                    node = node.parentElement;
                }
                return true;
            """, e)
            if ativo:
                resultado.append(e)
        return resultado

    def clicar(css):
        def tentar(d):
            from selenium.common.exceptions import (
                ElementClickInterceptedException, StaleElementReferenceException,
                ElementNotInteractableException,
            )
            try:
                elementos = visiveis(css)
                if not elementos:
                    return False
                elemento = elementos[0]
                driver.execute_script('arguments[0].scrollIntoView({block:"center"});', elemento)
                elemento.click()
                return True
            except (ElementClickInterceptedException, StaleElementReferenceException,
                    ElementNotInteractableException):
                return False
        wait.until(tentar)

    driver.get('https://www.discovercars.com/')
    if tempos: tempos.enter('location_seconds')
    log('Preenchendo o local. Se houver aviso de cookies, feche-o na janela.')
    wait.until(lambda d: visiveis('form.SearchModifier-Form input[name="PickupLocation"]') or False)
    overlays = visiveis('form.SearchModifier-Form .Autocomplete-LocationPickerOverlay')
    if overlays:
        log('Abrindo seletor de local no layout compacto...')
        clicar('form.SearchModifier-Form .Autocomplete-LocationPickerOverlay')
        seletor = '.SearchModifier-MobileLocationsModal.Modal-Container_isActive input[name="PickupLocation"]'
        wait.until(lambda d: visiveis(seletor) or False)
    else:
        seletor = 'form.SearchModifier-Form input[name="PickupLocation"]'
    clicar(seletor)
    campo = visiveis(seletor)[0]
    campo.send_keys(Keys.CONTROL + 'a')
    campo.send_keys(Keys.BACKSPACE)
    campo.send_keys(texto_busca_local(destino))
    anterior, desde = None, time.monotonic()

    def sugestoes_estaveis(d):
        nonlocal anterior, desde
        dados = [(e.get_attribute('data-label'), e.find_element(By.CSS_SELECTOR, '.Autocomplete-AutocompletePlace').text)
                 for e in visiveis('.Autocomplete-AutocompleteItem[data-label]')]
        if not dados or dados != anterior:
            anterior, desde = dados, time.monotonic()
            return False
        return dados if time.monotonic() - desde >= 2 else False

    opcoes = wait.until(sugestoes_estaveis)
    rotulo = escolher_rotulo(destino, opcoes)
    escolhido = next(e for e in visiveis('.Autocomplete-AutocompleteItem[data-label]')
                     if e.get_attribute('data-label') == rotulo)
    escolhido.click()

    def local_confirmado(d):
        textos = [e.get_attribute('value') or '' for e in visiveis('input[name="PickupLocation"]')]
        textos += [e.text for e in visiveis('.Autocomplete-SelectedLocation')]
        return normalizar_local(rotulo) in [normalizar_local(t) for t in textos]

    wait.until(local_confirmado)
    log('Local selecionado: ' + rotulo)
    if tempos: tempos.enter('dates_seconds')
    # A primeira versão por local faz devolução no mesmo ponto.
    for checkbox in visiveis('input[name="IsSameLocation"]'):
        if not checkbox.is_selected():
            checkbox.click()
    campos_data = wait.until(lambda d: visiveis('.DatePicker-CalendarField') or False)
    campos_data[0].click()
    wait.until(lambda d: visiveis('.rdrCalendarWrapper') or False)
    # O cabeçalho de datas fica oculto no layout móvel, mas registra
    # qual extremo do intervalo receberá o próximo clique no calendário.
    def fase_data(placeholder):
        return fase_calendario(visiveis, placeholder)

    wait.until(lambda d: fase_data('Early'))
    log('Calendário aberto: selecionando retirada e devolução pelos dias...')
    meses = ['January','February','March','April','May','June','July','August',
             'September','October','November','December']

    def clicar_dia(data):
        titulo = f'{meses[data.month-1]} {data.year}'
        candidatos = [m for m in visiveis('.rdrMonth')
                      if m.find_element(By.CSS_SELECTOR, '.rdrMonthName').text.strip() == titulo]
        if not candidatos:
            # innerText pode ficar vazio em meses fora da área visível.
            candidatos = [m for m in visiveis('.rdrMonth')
                          if (m.find_element(By.CSS_SELECTOR, '.rdrMonthName').get_attribute('textContent') or '').strip() == titulo]
        if not candidatos:
            raise ValueError('Mês não encontrado no calendário carregado: ' + titulo)
        for mes in candidatos:
            if not mes.is_displayed():
                continue
            for botao in mes.find_elements(By.CSS_SELECTOR, 'button.rdrDay'):
                classes = (botao.get_attribute('class') or '').split()
                numero = botao.find_element(By.CSS_SELECTOR, '.rdrDayNumber').get_attribute('textContent').strip()
                if numero == str(data.day) and 'rdrDayPassive' not in classes:
                    if 'rdrDayDisabled' in classes or not botao.is_enabled():
                        raise ValueError('Data indisponível no calendário: ' + data.isoformat())
                    driver.execute_script('arguments[0].scrollIntoView({block:"center"});', botao)
                    botao.click()
                    return
        raise ValueError('Dia não localizado no calendário ativo: ' + data.isoformat())

    clicar_dia(retirada)
    # O calendário deve passar da retirada para a devolução.
    wait.until(lambda d: fase_data('Continuous'))
    log('Retirada selecionada: ' + retirada.isoformat())
    clicar_dia(devolucao)
    log('Devolução selecionada: ' + devolucao.isoformat())
    botoes = driver.find_elements(By.XPATH, '//button[normalize-space(.)="Select dates"]')
    botao = next((b for b in botoes if b.is_displayed()), None)
    if botao is not None:
        botao.click()
    else:
        # No desktop a seleção da devolução fecha o calendário automaticamente.
        wait.until(lambda d: not visiveis('.rdrCalendarWrapper'))
    # Fixar os horários deste teste em 11h, sem assumir defaults silenciosamente.
    for indice in range(2):
        campos = visiveis('.SearchModifier-TimeSelect')
        if len(campos) != 2:
            raise ValueError('Não foi possível identificar os dois horários')
        if campos[indice].text.strip() != '11:00':
            campos[indice].click()
            def opcao_hora(d):
                for item in visiveis('.CustomSelect-MobileOption, .CustomSelect-SelectOption'):
                    if item.text.strip() == '11:00':
                        return item
                return False
            wait.until(opcao_hora).click()
    if tempos: tempos.enter('submit_seconds')
    log('Datas preenchidas; enviando a pesquisa...')
    wait.until(lambda d: next(iter(visiveis('button.SearchModifier-SubmitBtn')), False)).click()

    def resultado(d):
        if '/search/' not in urlparse(d.current_url).path:
            return False
        try:
            return ler_consulta(d.current_url)
        except ValueError:
            return False

    consulta = WebDriverWait(driver, 60).until(resultado)
    esperado_r = retirada.isoformat() + 'T11:00:00'
    esperado_d = devolucao.isoformat() + 'T11:00:00'
    if consulta['PickupDateTime'] != esperado_r or consulta['DropOffDateTime'] != esperado_d:
        raise ValueError('O site enviou datas/horários diferentes dos solicitados; coleta cancelada.')
    if consulta['PickupLocationId'] != consulta['DropOffLocationId']:
        raise ValueError('O site enviou locais diferentes para retirada e devolução.')
    if consulta['ResidenceCountry'] != 'BR' or consulta['DriverAge'] != 35:
        raise ValueError('Esta etapa usa residência Brasil e idade 35. Confira essas opções no site; coleta cancelada.')
    log('Consulta confirmada: ' + rotulo + ' | ' + esperado_r + ' → ' + esperado_d)
    return driver.current_url, consulta, rotulo


class TemposCarros:
    """Etapas exclusivas; primeiro lote e total são tempos acumulados."""
    def __init__(self, clock=None):
        self.clock = clock or time.monotonic
        self.started = self.last = self.clock()
        self.stage = 'validation_seconds'
        self.values = {}
    def enter(self, stage):
        now = self.clock()
        self.values[self.stage] = round(self.values.get(self.stage, 0) + now - self.last, 4)
        self.last, self.stage = now, stage
    def first_batch(self):
        if 'first_batch_seconds' not in self.values:
            self.values['first_batch_seconds'] = round(self.clock() - self.started, 4)
    def finish(self):
        self.enter('finished_seconds')
        self.values['total_seconds'] = round(self.last - self.started, 4)


def coletar_ofertas(destino, data_retirada, data_devolucao, limite_resultados, log=print):
    """Retorna registros e cobertura; usado pela TUI e pelo adaptador."""
    tempos = TemposCarros()
    ofertas, erros, consulta = {}, set(), None
    cobertura = 'Não identificado'
    motivo = 'timeout'
    driver = None
    pasta = Path.cwd() / 'resultados_carros'
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    try:
        url = destino.strip()
        retirada = datetime.strptime(data_retirada, '%Y-%m-%d').date()
        devolucao = datetime.strptime(data_devolucao, '%Y-%m-%d').date()
        if devolucao <= retirada:
            raise ValueError('A devolução precisa ser posterior à retirada.')
        por_link = url.startswith(('https://', 'http://'))
        consulta = None
        if por_link:
            if '/search/' not in urlparse(url).path:
                raise ValueError('Cole o link de resultados /search/ ou digite um local.')
            consulta = ler_consulta(url)
            if (datetime.fromisoformat(consulta['PickupDateTime']).date() != retirada or
                    datetime.fromisoformat(consulta['DropOffDateTime']).date() != devolucao):
                raise ValueError('As datas digitadas diferem das datas do link.')
        elif retirada < datetime.now().date():
            raise ValueError('A retirada não pode estar no passado.')
        limite = int(limite_resultados)
        if not 1 <= limite <= 100:
            raise ValueError('Escolha de 1 a 100 ofertas para este teste.')
        binary = shutil.which('chromium')
        if not binary:
            raise ValueError('Chromium não encontrado')
        options = webdriver.ChromeOptions()
        options.binary_location = binary
        options.add_argument('--window-size=1200,800')
        options.add_argument('--lang=en-US')
        options.add_argument('--ozone-platform=x11')
        tempos.enter('driver_seconds')
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        log('Abrindo consulta. Se houver aviso de cookies, feche-o na janela.')
        local_selecionado = 'Conforme link informado'
        tempos.enter('navigation_seconds')
        if por_link:
            driver.get(url)
        else:
            try:
                t_fast = time.monotonic()
                url, consulta, local_selecionado = criar_busca_direta(destino.strip(), retirada, devolucao, log)
                driver.get(url)
                tempos.values['fast_path_seconds'] = round(time.monotonic() - t_fast, 4)
                tempos.values['fast_path_used'] = 1
            except (ValueError, OSError, urllib.error.URLError, TimeoutError) as exc:
                log('Caminho rápido indisponível; usando formulário v12.1: ' + str(exc)[:240])
                tempos.values['fast_path_used'] = 0
                url, consulta, local_selecionado = abrir_busca_por_local(
                    driver, destino.strip(), retirada, devolucao, log, tempos)
        log('Datas conferidas: ' + consulta['PickupDateTime'] + ' → ' + consulta['DropOffDateTime'])
        tempos.enter('results_wait_seconds')
        wait = WebDriverWait(driver, 60)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR,'.SearchList-Card'))
        tempos.enter('sorting_seconds')
        log('Ordenando por preço...')
        def ordenado(d):
            # O valor do select sozinho não prova que a aplicação atualizou.
            # Exigir também o rótulo do botão que a interface apresenta.
            return d.execute_script("""
                const areas = [...document.querySelectorAll('.SearchSorting-SortingSelector')]
                    .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden');
                return areas.length > 0 && areas.every(area => {
                    const select = area.querySelector('select[aria-label="Sort by"]');
                    const button = area.querySelector('.SearchSorting-OpenSortingPopup');
                    return select && select.value === 'Price' && button &&
                        button.innerText.trim() === 'Price';
                });
            """)

        def selecionar_preco(d):
            # Em algumas larguras o select nativo fica oculto; o botão é visível.
            # Disparar o evento change do próprio controle permite ao site
            # reordenar e renderizar os resultados através de seu estado normal.
            return d.execute_script("""
                const areas = [...document.querySelectorAll('.SearchSorting-SortingSelector')]
                    .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden');
                let enviados = 0;
                for (const area of areas) {
                    const select = area.querySelector('select[aria-label="Sort by"]');
                    if (!select || ![...select.options].some(o => o.value === 'Price')) continue;
                    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
                    setter.call(select, 'Price');
                    select.dispatchEvent(new Event('input', {bubbles: true}));
                    select.dispatchEvent(new Event('change', {bubbles: true}));
                    enviados++;
                }
                return enviados > 0;
            """)

        try:
            if not ordenado(driver):
                WebDriverWait(driver, 15).until(selecionar_preco)
            WebDriverWait(driver, 20).until(ordenado)
            log('Price selecionado automaticamente e confirmado na interface.')
        except Exception:
            log('Não foi possível confirmar a seleção automática. Selecione Sort by → Price; aguardando 60 segundos...')
            wait.until(ordenado)
        tempos.enter('collection_seconds')
        log('Ordenação Price confirmada. Coletando ofertas estáveis...')
        ofertas, erros = {}, set()
        assinatura, desde = None, time.monotonic()
        inicio = time.monotonic()
        sem_novo = 0
        cobertura = 'Não identificado'
        while time.monotonic() - inicio < 180:
            if not ordenado(driver):
                raise ValueError('Ordenação mudou durante a coleta')
            # Detectar estabilidade com snapshot JS atômico. Só parsear page_source quando o lote estabilizar.
            sig = tuple(tuple(x) for x in snapshot_cards(driver))
            if not sig or sig != assinatura:
                assinatura, desde = sig, time.monotonic()
            elif time.monotonic() - desde >= 1.5:
                root = Document(driver.page_source).root
                # checked é propriedade dinâmica: consultar o navegador, não o HTML.
                cobertura_js = driver.execute_script("""
                    const e = document.querySelector('.CoverageTumbler input[type=\"checkbox\"]');
                    return e ? !!e.checked : null;
                """)
                atual = 'Incluída' if cobertura_js is True else 'Não incluída' if cobertura_js is False else 'Não identificado'
                if ofertas and atual != cobertura:
                    raise ValueError('Cobertura adicional mudou durante a coleta')
                cobertura = atual
                lote = []
                for card in root.select('SearchList-Card'):
                    try:
                        lote.append(extrair_card(card, consulta, driver.current_url))
                    except ValueError as exc:
                        erros.add(str(exc))
                antes = len(ofertas)
                for r in lote:
                    r.update(LocalSelecionado=local_selecionado, CoberturaAdicional=cobertura, ColetadoEm=datetime.now().astimezone().isoformat(),
                        Escopo='Menores totais entre ofertas coletadas; não garante todas as ofertas disponíveis')
                    ofertas[r['Link']] = r
                tempos.first_batch()
                log(f'Ofertas confirmadas: {len(ofertas)}/{limite}')
                if len(ofertas) >= limite:
                    motivo = 'result_limit'
                    break
                sem_novo = sem_novo+1 if len(ofertas)==antes else 0
                if sem_novo >= 5:
                    motivo = 'no_new_offers'
                    break
                driver.execute_script('window.scrollBy(0, Math.max(300, window.innerHeight * 0.65))')
                assinatura, desde = None, time.monotonic()
            time.sleep(.5)
        if not ofertas:
            raise ValueError('Nenhum total confirmado. ' + '; '.join(sorted(erros))[:600])
        tempos.enter('export_seconds')
        resultados = sorted(ofertas.values(), key=lambda r:r['TotalBRL'])[:limite]
        pasta.mkdir(exist_ok=True)
        path = pasta / f'discovercars_{stamp}.csv'
        with path.open('x', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=list(resultados[0]), delimiter=';')
            writer.writeheader()
            writer.writerows(resultados)
        log('Menores totais COLETADOS:')
        for r in resultados:
            log(f"{r['Modelo']} | {r['Locadora']} | {formatar_preco(r['TotalBRL'])}")
        log(f'Exportadas: {len(resultados)} | Limite solicitado: {limite} | Cobertura: {cobertura}')
        if len(resultados)<limite:
            log('Consulta parcial: não atingiu o limite solicitado.')
        for err in sorted(erros):
            log('Cartão não aproveitado: ' + err)
        log('CSV salvo: ' + str(path))
        return dict(resultados=resultados, consulta=consulta, erros=sorted(erros),
                    motivo=motivo, csv=str(path), ofertas_coletadas=len(ofertas), timings=tempos.values)
    except KeyboardInterrupt as exc:
        exc.car_timings = tempos.values
        raise
    except Exception as exc:
        exc.car_timings = tempos.values
        tempos.enter('diagnostic_seconds')
        log(f'FALHA: {type(exc).__name__}: {str(exc).split(chr(10) + "Stacktrace:")[0][:900]}')
        if driver:
            try:
                pasta.mkdir(exist_ok=True)
                import traceback
                (pasta / f'diagnostico_{stamp}.txt').write_text(traceback.format_exc(), encoding='utf-8')
                (pasta / f'diagnostico_{stamp}.html').write_text(driver.page_source, encoding='utf-8')
                driver.save_screenshot(str(pasta / f'diagnostico_{stamp}.png'))
                log('Diagnóstico salvo em ' + str(pasta))
            except Exception:
                pass
        raise
    finally:
        tempos.enter('cleanup_seconds')
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        tempos.finish()
        log('Tempos por etapa (segundos): ' + str(tempos.values))


def executar_scraper(destino, data_retirada, data_devolucao, limite_resultados, log_widget):
    app = log_widget.app
    def log(message):
        app.call_from_thread(log_widget.write_line, message)
    try:
        return coletar_ofertas(destino, data_retirada, data_devolucao, limite_resultados, log)
    except Exception:
        # O serviço já registrou a falha e o diagnóstico.
        return None
    finally:
        def liberar():
            app.buscando = False
            app.query_one('#btn_buscar', Button).disabled = False
        app.call_from_thread(liberar)


class RentalCarsScraperApp(App):

    CSS = """

    Screen {
        align: center middle;
        background: #1a1b26;
    }

    Container {
        width: 76;
        max-width: 100%;
        height: auto;
        max-height: 100%;
        overflow-y: auto;
        border: solid #7aa2f7;
        background: #24283b;
        padding: 1 2;
    }

    Label {
        margin-top: 1;
        color: #c0caf5;
        text-style: bold;
    }

    Input {
        background: #1f2335;
        border: solid #414868;
        color: #c0caf5;
        margin-bottom: 1;
    }

    Button {
        margin-top: 2;
        width: 100%;
        background: #41a7fc;
        color: #1a1b26;
    }

    Log {
        height: 16;
        margin-top: 1;
        background: #15161e;
        border: solid #414868;
    }

    """

    def compose(
        self
    ) -> ComposeResult:

        yield Header(
            show_clock=True
        )

        with Container():

            yield Label(
                "🚗 DiscoverCars Scraper"
            )

            yield Label(
                "Local específico ou link (ex.: Ibiza Airport):"
            )

            yield Input(
                placeholder="Ibiza Airport",
                id="destino"
            )

            yield Label("Por local: 11h → 11h · Brasil · idade 35 · devolução no mesmo local")

            yield Label(
                "Retirada (AAAA-MM-DD):"
            )

            yield Input(
                placeholder="2026-09-12",
                id="retirada"
            )

            yield Label(
                "Devolução (AAAA-MM-DD):"
            )

            yield Input(
                placeholder="2026-09-13",
                id="devolucao"
            )

            yield Label(
                "Máximo de resultados:"
            )

            yield Input(
                value="10",
                id="limite"
            )

            yield Button(
                "Buscar Melhores Tarifas",
                id="btn_buscar"
            )

            yield Log(
                id="console_log"
            )

    def on_button_pressed(
        self,
        event: Button.Pressed
    ) -> None:

        if event.button.id != "btn_buscar":
            return

        destino = self.query_one(
            "#destino"
        ).value.strip()

        data_r = self.query_one(
            "#retirada"
        ).value.strip()

        data_d = self.query_one(
            "#devolucao"
        ).value.strip()

        limite = self.query_one(
            "#limite"
        ).value.strip()

        log = self.query_one(
            "#console_log"
        )

        if not destino:

            log.write_line(
                "[🚨] Digite o local ou cole o link da consulta!"
            )

            return

        if not limite:
            limite = "10"

        log.clear()

        log.write_line(
            "[🚗] Nova pesquisa"
        )

        log.write_line(
            f"[📍] {destino}"
        )

        log.write_line(
            f"[📅] {data_r} → {data_d}"
        )

        log.write_line(
            f"[🔢] Top {limite}"
        )

        if getattr(self, "buscando", False):
            log.write_line("Já existe uma consulta em execução.")
            return
        self.buscando = True
        self.query_one("#btn_buscar", Button).disabled = True

        self.run_worker(

            lambda: executar_scraper(
                destino,
                data_r,
                data_d,
                limite,
                log
            ),

            exclusive=True,

            thread=True
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    RentalCarsScraperApp().run()

