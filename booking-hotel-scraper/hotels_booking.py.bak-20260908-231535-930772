import tkinter as tk
from tkinter import messagebox
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import pandas as pd
import time
import re
from geopy.distance import geodesic

def create_driver():
    options = webdriver.ChromeOptions()

    # Chromium no Arch
    options.binary_location = "/usr/bin/chromium"

    # Descomente a linha abaixo se quiser rodar sem abrir a janela do navegador
    # options.add_argument("--headless=new")

    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    # Flags importantes no Linux / Arch
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--window-size=1920,1080")

    service = ChromeService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    return webdriver.Chrome(service=service, options=options)

def scroll_until_all_hotels_loaded(driver, max_wait_time=60):
    SCROLL_PAUSE_TIME = 2.5
    last_count = 0
    start_time = time.time()

    while True:
        driver.execute_script("window.scrollBy(0, 2000);")
        time.sleep(SCROLL_PAUSE_TIME)

        hotels = driver.find_elements(By.XPATH, '//div[@data-testid="property-card"]')
        current_count = len(hotels)
        print(f"Hotéis visíveis: {current_count}")

        if current_count > last_count:
            last_count = current_count
            start_time = time.time()
        else:
            if time.time() - start_time > max_wait_time:
                print("⏹️ Parou de rolar: nenhum hotel novo após 60 segundos.")
                break

    return hotels

NOT_INFORMED = "Não informado"
REFERENCE_COORDS = (-22.5113, -43.1779)
REFERENCE_NAME = "Ponto de referência em Petrópolis (-22.5113, -43.1779)"


def first_text(root, selectors):
    for selector in selectors:
        for element in root.find_elements(By.CSS_SELECTOR, selector):
            text = element.text.strip()
            if text:
                return text
    return ""


def parse_price(raw):
    """Aceita somente valor identificado como BRL; mantém o texto para auditoria."""
    match = re.fullmatch(r"\s*(?:R\$|BRL)\s*([0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2})?)\s*", raw)
    if not match:
        return None, NOT_INFORMED
    value = float(match.group(1).replace(".", "").replace(",", "."))
    return (value, "BRL") if value > 0 else (None, "BRL")


def price_with_taxes(price, currency, taxes_text):
    """Total dos valores exibidos; não presume taxa zero quando não informada."""
    if price is None or currency != 'BRL':
        return None, None, 'Preço ou moeda não confirmado'
    if re.fullmatch(r'\s*Impostos e taxas incluídos\s*', taxes_text, re.I):
        return 0.0, price, 'Taxas incluídas no preço exibido'
    match = re.fullmatch(
        r'\s*\+\s*(R\$\s*[0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2})?)\s+em impostos e taxas\s*',
        taxes_text, re.I)
    if match:
        extra, _ = parse_price(match.group(1))
        if extra is not None:
            return extra, round(price + extra, 2), 'Preço exibido + taxas adicionais exibidas'
    return None, None, 'Total não confirmado: verificar taxas na página'


def extract_stars(card):
    for container in card.find_elements(By.CSS_SELECTOR, '[data-testid="rating-stars"]'):
        for element in [container] + container.find_elements(By.CSS_SELECTOR, '[aria-label], [title]'):
            for attribute in ('aria-label', 'title'):
                label = element.get_attribute(attribute) or ""
                match = re.search(r'\b([1-5])\s*(?:estrelas?|stars?)\b', label, re.I)
                if match:
                    return int(match.group(1))
    return NOT_INFORMED


def extract_hotels(driver):
    hotels = scroll_until_all_hotels_loaded(driver)
    hotel_list = []
    for hotel in hotels:
        raw_price = first_text(hotel, ['[data-testid="price-and-discounted-price"]'])
        price, currency = parse_price(raw_price)
        score = None
        # Preserva o seletor que funcionou no primeiro teste; valida a faixa.
        raw_score = first_text(hotel, ['div.f63b14ab7a'])
        if re.fullmatch(r'\d{1,2}(?:[.,]\d)?', raw_score):
            score = float(raw_score.replace(',', '.'))
        if score is None or not 0 <= score <= 10:
            raw_score = first_text(hotel, ['[data-testid="review-score"]'])
            match = re.search(r'(?:Com nota|Pontuação|Scored|Nota)\s*([0-9]+(?:[.,][0-9])?)', raw_score, re.I)
            score = float(match.group(1).replace(',', '.')) if match else None
        if score is not None and not 0 <= score <= 10:
            score = None
        links = hotel.find_elements(By.CSS_SELECTOR, '[data-testid="title-link"]')
        url = links[0].get_attribute('href') if links else None
        hotel_list.append({
            'Hotel Name': first_text(hotel, ['[data-testid="title"]']) or NOT_INFORMED,
            'Stars': extract_stars(hotel),
            'Price': price,
            'Currency': currency,
            'Price Text': raw_price or NOT_INFORMED,
            'Price Status': 'Extraído do cartão' if price is not None else 'Não confirmado',
            'Stay Text': first_text(hotel, ['[data-testid="price-for-x-nights"]']) or NOT_INFORMED,
            'Taxes Text': first_text(hotel, ['[data-testid="taxes-and-charges"]']) or NOT_INFORMED,
            'Room Text': first_text(hotel, ['[data-testid="recommended-unit"]']) or NOT_INFORMED,
            'Review Score (/10)': score,
            'Hotel URL': url or NOT_INFORMED,
        })
    return hotel_list


def address_from_jsonld(value):
    """Lê PostalAddress de uma hospedagem, sem confundir endereço da plataforma."""
    lodging_types = {'Hotel', 'LodgingBusiness', 'Hostel', 'Motel', 'Resort',
                     'BedAndBreakfast', 'VacationRental', 'Accommodation'}
    if isinstance(value, list):
        for child in value:
            address = address_from_jsonld(child)
            if address:
                return address
    if isinstance(value, dict):
        types = value.get('@type', [])
        if isinstance(types, str):
            types = [types]
        if lodging_types.intersection(types):
            address = value.get('address')
            if isinstance(address, str):
                return address.strip()
            if isinstance(address, dict):
                parts = []
                def normalizar(text):
                    import unicodedata
                    text = unicodedata.normalize('NFKD', str(text).casefold())
                    return re.sub(r'[^a-z0-9]', '', text)
                for key in ('streetAddress', 'addressLocality', 'addressRegion', 'postalCode', 'addressCountry'):
                    part = address.get(key)
                    if isinstance(part, dict):
                        part = part.get('name')
                    if not part:
                        continue
                    part = str(part).strip()
                    normalized = normalizar(part)
                    if normalized and not any(normalized in normalizar(old) for old in parts):
                        parts = [old for old in parts if normalizar(old) not in normalized]
                        parts.append(part)
                if parts:
                    return ', '.join(parts)
        for key in ('@graph', 'mainEntity', 'mainEntityOfPage'):
            address = address_from_jsonld(value.get(key))
            if address:
                return address
    return ""


def fetch_details(driver, url):
    import json
    driver.get(url)
    latitude = longitude = None
    try:
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "map_trigger_header_pin")))
        latlng = element.get_attribute("data-atlas-latlng")
        if latlng:
            latitude, longitude = map(float, latlng.split(','))
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                latitude = longitude = None
    except Exception:
        pass

    address = ""
    for element in driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]'):
        try:
            address = address_from_jsonld(json.loads(element.get_attribute('textContent') or 'null'))
        except (ValueError, TypeError):
            continue
        if address:
            break
    if not address:
        address = first_text(driver, ['[data-testid="address"]',
                                     '[data-testid="property-address"]',
                                     '#hotel_address', '.hp_address_subtitle',
                                     '[data-node_tt_id="location_score_tooltip"]'])
    return latitude, longitude, address or NOT_INFORMED


def calculate_distance(hotel_coords, event_coords):
    try:
        return round(geodesic(hotel_coords, event_coords).kilometers, 2)
    except (ValueError, TypeError):
        return None


def validate_search(destination, checkin, checkout):
    from datetime import datetime
    if not destination.strip():
        raise ValueError('Informe o destino.')
    for value in (checkin, checkout):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('Use datas no formato YYYY-MM-DD.')
    arrival = datetime.strptime(checkin, '%Y-%m-%d')
    departure = datetime.strptime(checkout, '%Y-%m-%d')
    if departure <= arrival:
        raise ValueError('O check-out deve ser posterior ao check-in.')
    return (departure - arrival).days


def is_petropolis(destination):
    import unicodedata
    value = ''.join(c for c in unicodedata.normalize('NFD', destination.lower().strip())
                    if unicodedata.category(c) != 'Mn')
    return value == 'petropolis'


def run_scraping(destination, checkin, checkout, *, return_records=False):
    from datetime import datetime
    from pathlib import Path
    from urllib.parse import urlencode
    import os
    import tempfile

    destination = destination.strip()
    nights = validate_search(destination, checkin, checkout)
    reference = REFERENCE_COORDS if is_petropolis(destination) else None
    params = dict(ss=destination, checkin=checkin, checkout=checkout,
                  group_adults=2, no_rooms=1, group_children=0,
                  nflt='ht_id=204', selected_currency='BRL')
    url = 'https://www.booking.com/searchresults.pt-br.html?' + urlencode(params)
    driver = create_driver()
    hotels = []
    try:
        driver.set_page_load_timeout(60)
        driver.get(url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//div[@data-testid="property-card"]')))
        hotels = extract_hotels(driver)
        if not hotels:
            raise RuntimeError('Nenhum cartão de hospedagem foi extraído.')
        print(f'\n{len(hotels)} hospedagens encontradas em {destination}.', flush=True)
        for idx, hotel in enumerate(hotels, 1):
            print(f"Processando {idx}/{len(hotels)}: {hotel['Hotel Name']}", flush=True)
            lat = lon = None
            address = NOT_INFORMED
            error = ''
            if hotel['Hotel URL'] != NOT_INFORMED:
                try:
                    lat, lon, address = fetch_details(driver, hotel['Hotel URL'])
                except Exception as exc:
                    error = str(exc)
                    print(f'  Falha nos detalhes; preço do cartão preservado: {exc}', flush=True)
            if error:
                detail_status = 'Falha ao consultar detalhes'
            elif address == NOT_INFORMED or lat is None or lon is None:
                detail_status = 'Detalhes parciais'
            else:
                detail_status = 'Endereço e coordenadas extraídos'
            hotel.update({
                'Destination': destination, 'Check-in': checkin, 'Check-out': checkout,
                'Nights': nights, 'Adults': 2, 'Children': 0, 'Rooms': 1,
                'Requested Currency': 'BRL',
                'Price Basis': 'Valor exibido no cartão; conferir Stay Text e Taxes Text',
                'Latitude': lat, 'Longitude': lon, 'Address': address,
                'Geodesic Distance to Reference (Km)': (
                    calculate_distance((lat, lon), reference)
                    if reference and lat is not None and lon is not None else None),
                'Distance Reference': REFERENCE_NAME if reference else 'Não configurada para este destino',
                'Distance Method': 'Geográfica (geodésica), não trajeto por ruas',
                'Details Status': detail_status, 'Details Error': error,
                'Collected At': datetime.now().astimezone().isoformat(timespec='seconds'),
            })
    finally:
        driver.quit()

    # Ordena por total com taxas; totais desconhecidos permanecem no fim.
    for hotel in hotels:
        additional, total, status = price_with_taxes(
            hotel['Price'], hotel['Currency'], hotel['Taxes Text'])
        hotel['Additional Taxes (BRL)'] = additional
        hotel['Total Displayed (BRL)'] = total
        hotel['Total Status'] = status
    df = pd.DataFrame(hotels).sort_values(
        ['Total Displayed (BRL)', 'Price'], ascending=True, na_position='last', kind='stable')
    safe_name = re.sub(r'[^\w .-]', '_', destination).strip(' .') or 'destino'
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    filename = Path(f'Hotels - {safe_name} - {checkin} - {checkout} - {stamp}.xlsx').resolve()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=filename.parent, suffix='.xlsx', delete=False) as f:
            temporary = f.name
        df.to_excel(temporary, index=False)
        os.replace(temporary, filename)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    valid = int(df['Price'].notna().sum())
    addresses = int((df['Address'] != NOT_INFORMED).sum())
    stars = int((df['Stars'] != NOT_INFORMED).sum())
    totals = int(df['Total Displayed (BRL)'].notna().sum())
    print(f'\nExportadas: {len(df)} | Com preço: {valid} | Totais: {totals} | Endereços: {addresses} | Estrelas: {stars}', flush=True)
    print(f'Arquivo salvo: {filename}', flush=True)
    if return_records:
        return {"records": hotels, "excel": str(filename), "search_url": url}
    return len(df), str(filename)


def on_submit():
    destination = entry_destination.get()
    checkin = entry_checkin.get()
    checkout = entry_checkout.get()

    if not all([destination, checkin, checkout]):
        messagebox.showerror("Erro", "Preencha todos os campos.")
        return

    try:
        count, file = run_scraping(destination, checkin, checkout)
        messagebox.showinfo("Concluído", f"{count} hospedagens exportadas.\nArquivo salvo: {file}")
    except Exception as e:
        messagebox.showerror("Erro", str(e))

# ==================== INTERFACE ====================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Booking Hotel Scraper")
    root.geometry("520x460")          # ← aumentei a altura
    root.configure(bg="#1e1e2e")
    root.resizable(False, False)

    # Cores
    BG = "#1e1e2e"
    FG = "#cdd6f4"
    ACCENT = "#89b4fa"
    ENTRY_BG = "#313244"
    BUTTON_BG = "#89b4fa"
    BUTTON_FG = "#1e1e2e"

    # Fonte
    FONT_TITLE = ("JetBrains Mono", 14, "bold")
    FONT_LABEL = ("JetBrains Mono", 11)
    FONT_ENTRY = ("JetBrains Mono", 12)

    # Título
    title = tk.Label(
        root,
        text="🏨  Booking Hotel Scraper",
        font=FONT_TITLE,
        bg=BG,
        fg=ACCENT
    )
    title.pack(pady=(25, 15))

    # Frame principal
    frame = tk.Frame(root, bg=BG)
    frame.pack(padx=40, fill="x")

    def create_field(parent, label_text):
        lbl = tk.Label(parent, text=label_text, font=FONT_LABEL, bg=BG, fg=FG, anchor="w")
        lbl.pack(fill="x", pady=(10, 3))

        entry = tk.Entry(
            parent,
            font=FONT_ENTRY,
            bg=ENTRY_BG,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#45475a",
            highlightcolor=ACCENT
        )
        entry.pack(fill="x", ipady=7)
        return entry

    entry_destination = create_field(frame, "Destination")
    entry_checkin = create_field(frame, "Check-in  (YYYY-MM-DD)")
    entry_checkout = create_field(frame, "Check-out (YYYY-MM-DD)")

    # Botão
    btn = tk.Button(
        root,
        text="▶  Start Scraping",
        font=("JetBrains Mono", 12, "bold"),
        bg=BUTTON_BG,
        fg=BUTTON_FG,
        activebackground="#74c7ec",
        activeforeground=BUTTON_FG,
        relief="flat",
        cursor="hand2",
        command=on_submit,
        padx=25,
        pady=12
    )
    btn.pack(pady=(25, 15))

    # Rodapé
    footer = tk.Label(
        root,
        text="Arch Linux  •  Selenium + Booking.com",
        font=("JetBrains Mono", 9),
        bg=BG,
        fg="#6c7086"
    )
    footer.pack(side="bottom", pady=12)

    root.mainloop()
