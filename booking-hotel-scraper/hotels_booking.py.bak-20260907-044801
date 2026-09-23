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

def extract_hotels(driver):
    hotels = scroll_until_all_hotels_loaded(driver)
    hotel_list = []

    for hotel in hotels:
        data = {}

        try:
            data['Hotel Name'] = hotel.find_element(By.XPATH, './/div[@data-testid="title"]').text
        except:
            data['Hotel Name'] = 'N/A'

        try:
            stars = len(hotel.find_elements(By.XPATH, './/div[@data-testid="rating-stars"]/span'))
            data['Stars'] = stars
        except:
            data['Stars'] = 'N/A'

        try:
            price = hotel.find_element(By.XPATH, './/span[@data-testid="price-and-discounted-price"]').text
            price_clean = re.sub(r'[^\d,]', '', price).replace(',', '.')
            data['Price'] = float(price_clean) if price_clean else 'N/A'
        except:
            data['Price'] = 'N/A'

        try:
            note_elem = hotel.find_element(By.XPATH, './/div[contains(@class, "f63b14ab7a")]')
            note = note_elem.text.strip()
            data['Review Score (/10)'] = float(note.replace(',', '.'))
        except:
            data['Review Score (/10)'] = 'N/A'

        try:
            link = hotel.find_element(By.XPATH, './/a[@data-testid="title-link"]').get_attribute("href")
            data['Hotel URL'] = link
        except:
            data['Hotel URL'] = 'N/A'

        hotel_list.append(data)

    return hotel_list

def fetch_details(driver, url):
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "map_trigger_header_pin"))
        )
        latlng_element = driver.find_element(By.ID, "map_trigger_header_pin")
        latlng = latlng_element.get_attribute("data-atlas-latlng")
        latitude, longitude = map(float, latlng.split(',')) if latlng else (None, None)
    except:
        latitude, longitude = None, None

    return latitude, longitude, 'Address not available'

def calculate_distance(hotel_coords, event_coords):
    try:
        return round(geodesic(hotel_coords, event_coords).kilometers, 2)
    except:
        return 'Error'

def run_scraping(destination, checkin, checkout):
    driver = create_driver()

    # Coordenadas de referência (opcional - troque se quiser calcular distância de um ponto específico)
    # Exemplo: centro de Petrópolis
    event_coords = (-22.5113, -43.1779)

    url = f'https://www.booking.com/searchresults.pt-br.html?ss={destination}&checkin={checkin}&checkout={checkout}&group_adults=2&no_rooms=1&group_children=0&nflt=ht_id%3D204'
    driver.get(url)

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, '//div[@data-testid="property-card"]'))
    )

    hotels = extract_hotels(driver)
    print(f"\n{len(hotels)} hotéis encontrados em {destination}.\n")

    for idx, hotel in enumerate(hotels):
        print(f"Processando {idx+1}/{len(hotels)}: {hotel['Hotel Name']}")
        if hotel['Hotel URL'] != 'N/A':
            lat, lon, address = fetch_details(driver, hotel['Hotel URL'])
            hotel['Latitude'] = lat if lat else 'N/A'
            hotel['Longitude'] = lon if lon else 'N/A'
            hotel['Address'] = address
            if lat and lon:
                hotel['Distance to Event (Km)'] = calculate_distance((lat, lon), event_coords)
            else:
                hotel['Distance to Event (Km)'] = 'Coordinates not available'
        else:
            hotel['Latitude'] = hotel['Longitude'] = hotel['Address'] = hotel['Distance to Event (Km)'] = 'N/A'

    df = pd.DataFrame(hotels)

    # Ordena pelo preço (do mais barato para o mais caro)
    if 'Price' in df.columns:
        df = df[df['Price'] != 'N/A'].sort_values(by='Price', ascending=True)

    filename = f'Hotels - {destination} - {checkin} - {checkout}.xlsx'
    df.to_excel(filename, index=False)
    driver.quit()

    return len(hotels), filename

def on_submit():
    destination = entry_destination.get()
    checkin = entry_checkin.get()
    checkout = entry_checkout.get()

    if not all([destination, checkin, checkout]):
        messagebox.showerror("Erro", "Preencha todos os campos.")
        return

    try:
        count, file = run_scraping(destination, checkin, checkout)
        messagebox.showinfo("Concluído", f"{count} hotéis recuperados.\nArquivo salvo: {file}")
    except Exception as e:
        messagebox.showerror("Erro", str(e))

# ==================== INTERFACE ====================
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
