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
from datetime import datetime
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urljoin

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


def abrir_busca_por_local(driver, destino, retirada, devolucao, log):
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


def coletar_ofertas(destino, data_retirada, data_devolucao, limite_resultados, log=print):
    """Retorna registros e cobertura; usado pela TUI e pelo adaptador."""
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
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        log('Abrindo consulta. Se houver aviso de cookies, feche-o na janela.')
        local_selecionado = 'Conforme link informado'
        if por_link:
            driver.get(url)
        else:
            url, consulta, local_selecionado = abrir_busca_por_local(
                driver, destino.strip(), retirada, devolucao, log)
        log('Datas conferidas: ' + consulta['PickupDateTime'] + ' → ' + consulta['DropOffDateTime'])
        wait = WebDriverWait(driver, 60)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR,'.SearchList-Card'))
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
        log('Ordenação Price confirmada. Coletando ofertas estáveis...')
        ofertas, erros = {}, set()
        assinatura, desde = None, time.monotonic()
        inicio = time.monotonic()
        sem_novo = 0
        cobertura = 'Não identificado'
        while time.monotonic() - inicio < 180:
            if not ordenado(driver):
                raise ValueError('Ordenação mudou durante a coleta')
            root = Document(driver.page_source).root
            checks = [n for n in root.all() if n.tag == 'input' and 'Full Coverage' in n.attrs.get('aria-label','')]
            # checked é propriedade dinâmica: consultar o navegador, não o HTML.
            ce = driver.find_elements(By.CSS_SELECTOR,'.CoverageTumbler input[type="checkbox"]')
            atual = ('Incluída' if ce[0].is_selected() else 'Não incluída') if ce else 'Não identificado'
            if ofertas and atual != cobertura:
                raise ValueError('Cobertura adicional mudou durante a coleta')
            cobertura = atual
            lote = []
            for card in root.select('SearchList-Card'):
                try:
                    lote.append(extrair_card(card, consulta, driver.current_url))
                except ValueError as exc:
                    erros.add(str(exc))
            sig = tuple((r['Link'],str(r['TotalBRL'])) for r in lote)
            if not sig or sig != assinatura:
                assinatura, desde = sig, time.monotonic()
            elif time.monotonic() - desde >= 3:
                antes = len(ofertas)
                for r in lote:
                    r.update(LocalSelecionado=local_selecionado, CoberturaAdicional=cobertura, ColetadoEm=datetime.now().astimezone().isoformat(),
                        Escopo='Menores totais entre ofertas coletadas; não garante todas as ofertas disponíveis')
                    ofertas[r['Link']] = r
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
                    motivo=motivo, csv=str(path), ofertas_coletadas=len(ofertas))
    except Exception as exc:
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
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


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

