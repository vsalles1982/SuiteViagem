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
    options.binary_location = "/usr/bin/chromium"
    # options.add_argument("--headless=new")
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--window-size=1920,1080")

    service = ChromeService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    return webdriver.Chrome(service=service, options=options)

def scroll_until_all_hotels_loaded(driver, max_wait_time=45):
    SCROLL_PAUSE_TIME = 2.0
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
                print("⏹️ Parou de rolar.")
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
            data['Stars'] = 0

        try:
            price_elem = hotel.find_element(By.XPATH, './/span[@data-testid="price-and-discounted-price"]')
            price_text = price_elem.text
            price_clean = re.sub(r'[^\d,]', '', price_text).replace(',', '.')
            data['Price'] = float(price_clean) if price_clean else None
            data['Price_Text'] = price_text   # guarda o texto original também
        except:
            data['Price'] = None
            data['Price_Text'] = 'N/A'

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

def run_scraping(destination, checkin, checkout):
    driver = create_driver()

    url = f'https://www.booking.com/searchresults.pt-br.html?ss={destination}&checkin={checkin}&checkout={checkout}&group_adults=2&no_rooms=1&group_children=0&nflt=ht_id%3D204'
    driver.get(url)

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, '//div[@data-testid="property-card"]'))
    )

    hotels = extract_hotels(driver)
    print(f"\n{len(hotels)} hotéis encontrados em {destination}.\n")
    print("-" * 70)

    # Mostra preço enquanto processa
    for idx, hotel in enumerate(hotels, 1):
        price_show = hotel.get('Price_Text', 'N/A')
        stars = hotel.get('Stars', 0)
        print(f"{idx:2d}/ {hotel['Hotel Name'][:45]:<45} | {stars}★ | {price_show}")

    driver.quit()

    # DataFrame e ordenação
    df = pd.DataFrame(hotels)
    df = df[df['Price'].notna()].copy()
    df = df.sort_values(by='Price', ascending=True).reset_index(drop=True)

    # === TOP 10 MAIS BARATOS ===
    print("\n" + "="*70)
    print(f"TOP 10 MAIS BARATOS - {destination.upper()}")
    print(f"Check-in: {checkin}  |  Check-out: {checkout}")
    print("="*70)

    top10 = df.head(10)
    for i, row in top10.iterrows():
        print(f"{i+1:2d}. {row['Hotel Name'][:50]:<50} | {row['Stars']}★ | {row['Price_Text']}")

    print("="*70)

    # Salva Excel completo
    filename = f'Hotels - {destination} - {checkin} - {checkout}.xlsx'
    df.to_excel(filename, index=False)
    print(f"\nArquivo completo salvo: {filename}")

    return len(df), filename

def on_submit():
    destination = entry_destination.get().strip()
    checkin = entry_checkin.get().strip()
    checkout = entry_checkout.get().strip()

    if not all([destination, checkin, checkout]):
        messagebox.showerror("Erro", "Preencha todos os campos.")
        return

    try:
        count, file = run_scraping(destination, checkin, checkout)
        messagebox.showinfo("Concluído", f"{count} hotéis com preço.\nArquivo: {file}\n\nVeja o TOP 10 no terminal!")
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
