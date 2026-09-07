"""DiscoverCars: consulta por URL, datas conferidas e totais em BRL.
Primeira etapa: configure local, horários, residência e idade no site e cole
seu link /search/. Não automatiza o calendário nesta versão.
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
from selenium.webdriver.support.ui import WebDriverWait, Select


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


def executar_scraper(destino, data_retirada, data_devolucao, limite_resultados, log_widget):
    app = log_widget.app
    def log(message):
        app.call_from_thread(log_widget.write_line, message)
    driver = None
    pasta = Path.cwd() / 'resultados_carros'
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    try:
        url = destino.strip()
        if '/search/' not in urlparse(url).path:
            raise ValueError('Cole o link da página de resultados /search/.')
        consulta = ler_consulta(url)
        for field, expected in [('PickupDateTime',data_retirada),('DropOffDateTime',data_devolucao)]:
            date = datetime.strptime(expected, '%Y-%m-%d').date()
            if datetime.fromisoformat(consulta[field]).date() != date:
                raise ValueError('As datas digitadas diferem das datas do link. Gere a consulta correta no site.')
        limite = int(limite_resultados)
        if not 1 <= limite <= 100:
            raise ValueError('Escolha de 1 a 100 ofertas para este teste.')
        log('Datas conferidas no link: ' + consulta['PickupDateTime'] + ' → ' + consulta['DropOffDateTime'])
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
        driver.get(url)
        wait = WebDriverWait(driver, 60)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR,'.SearchList-Card'))
        log('Ordenando por preço...')
        def ordenar(d):
            for el in d.find_elements(By.CSS_SELECTOR,'select[aria-label="Sort by"]'):
                try:
                    if el.is_displayed():
                        Select(el).select_by_value('Price')
                        return True
                except Exception:
                    continue
            return False
        try:
            WebDriverWait(driver, 10).until(ordenar)
        except Exception:
            log('Selecione manualmente Sort by → Price. Aguardando até 60 segundos...')
        def ordenado(d):
            els = d.find_elements(By.CSS_SELECTOR, 'select[aria-label="Sort by"]')
            return bool(els) and all(e.get_attribute('value') == 'Price' for e in els)
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
                    r.update(CoberturaAdicional=cobertura, ColetadoEm=datetime.now().astimezone().isoformat(),
                        Escopo='Menores totais entre ofertas coletadas; não garante todas as ofertas disponíveis')
                    ofertas[r['Link']] = r
                log(f'Ofertas confirmadas: {len(ofertas)}/{limite}')
                if len(ofertas) >= limite:
                    break
                sem_novo = sem_novo+1 if len(ofertas)==antes else 0
                if sem_novo >= 5:
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
    except Exception as exc:
        log(f'FALHA: {type(exc).__name__}: {str(exc)[:700]}')
        if driver:
            try:
                pasta.mkdir(exist_ok=True)
                (pasta / f'diagnostico_{stamp}.html').write_text(driver.page_source, encoding='utf-8')
                driver.save_screenshot(str(pasta / f'diagnostico_{stamp}.png'))
                log('Diagnóstico salvo em ' + str(pasta))
            except Exception:
                pass
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
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
        width: 64;
        height: auto;
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
                "Link da consulta (datas e local definidos no site):"
            )

            yield Input(
                placeholder="Cole o link completo /search/ do DiscoverCars",
                id="destino"
            )

            yield Label(
                "Confirme a retirada (AAAA-MM-DD):"
            )

            yield Input(
                placeholder="2026-09-12",
                id="retirada"
            )

            yield Label(
                "Confirme a devolução (AAAA-MM-DD):"
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
                "[🚨] Cole o link da consulta!"
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
