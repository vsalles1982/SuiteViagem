def executar_scraper(destino, data_retirada, data_devolucao, limite_resultados, log_widget):
    log_widget.write_line("[⚙️] Inicializando o Chromium...")

    options = webdriver.ChromeOptions()
    options.binary_location = "/usr/sbin/chromium"
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")

    driver = webdriver.Chrome(options=options)

    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)

    dados_carros = []

    try:
        log_widget.write_line("[🌐] Acessando DiscoverCars...")
        driver.get("https://www.discovercars.com/")
        wait = WebDriverWait(driver, 25)
        time.sleep(3)

        # Cookies
        try:
            cookie = driver.find_element(By.XPATH, "//button[contains(., 'Accept') or contains(., 'Agree') or contains(., 'Aceitar')]")
            cookie.click()
            time.sleep(1)
        except:
            pass

        log_widget.write_line(f"[📍] Tentando preencher: {destino}")

        # ========== FORÇA O PREENCHIMENTO ==========
        # 1. Encontra todos os inputs de texto
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input:not([type])")
        log_widget.write_line(f"[DEBUG] Encontrei {len(inputs)} inputs na página")

        location_input = None
        for inp in inputs:
            try:
                ph = (inp.get_attribute("placeholder") or "").lower()
                if any(x in ph for x in ["airport", "city", "enter", "pick", "location", "destino"]):
                    location_input = inp
                    log_widget.write_line(f"[DEBUG] Input encontrado com placeholder: {ph}")
                    break
            except:
                continue

        if not location_input:
            # Fallback: pega o primeiro input visível
            for inp in inputs:
                if inp.is_displayed():
                    location_input = inp
                    log_widget.write_line("[DEBUG] Usando o primeiro input visível")
                    break

        if not location_input:
            raise Exception("Nenhum input de localização encontrado")

        # 2. Clica com ActionChains
        ActionChains(driver).move_to_element(location_input).click().perform()
        time.sleep(0.6)

        # 3. Limpa
        location_input.clear()
        location_input.send_keys(Keys.CONTROL + "a")
        location_input.send_keys(Keys.DELETE)
        time.sleep(0.3)

        # 4. Digita normalmente
        location_input.send_keys(destino)
        time.sleep(1.5)

        # 5. Força via JavaScript também (caso o React não tenha capturado)
        driver.execute_script("""
            arguments[0].value = arguments[1];
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """, location_input, destino)

        time.sleep(2.5)
        log_widget.write_line("[DEBUG] Texto enviado. Aguardando sugestões...")

        # Tenta clicar na primeira sugestão
        try:
            sugestoes = wait.until(EC.presence_of_all_elements_located((
                By.XPATH, "//ul//li | //div[contains(@class,'suggestion') or contains(@class,'dropdown')]//li | //li[@role='option']"
            )))
            if sugestoes:
                sugestoes[0].click()
                log_widget.write_line("[✅] Sugestão clicada")
            else:
                location_input.send_keys(Keys.ARROW_DOWN)
                time.sleep(0.3)
                location_input.send_keys(Keys.ENTER)
                log_widget.write_line("[⚠️] Selecionado via teclado")
        except Exception as e:
            log_widget.write_line(f"[⚠️] Nenhuma sugestão clara: {e}")
            location_input.send_keys(Keys.ENTER)

        time.sleep(1.5)

        # ========== BOTÃO SEARCH ==========
        log_widget.write_line("[🔍] Procurando botão Search now...")

        try:
            btn = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[contains(., 'Search now') or contains(., 'Search')]"
            )))
            btn.click()
            log_widget.write_line("[✅] Botão Search clicado")
        except:
            # Fallback
            btns = driver.find_elements(By.TAG_NAME, "button")
            for b in btns:
                if "search" in (b.text or "").lower():
                    b.click()
                    log_widget.write_line("[✅] Botão encontrado por texto")
                    break

        # ========== RESULTADOS ==========
        log_widget.write_line("[⏳] Aguardando resultados...")
        time.sleep(6)

        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)

        # Tenta vários seletores de cards
        car_cards = driver.find_elements(By.XPATH,
            "//div[contains(@class,'car') or contains(@class,'offer') or contains(@class,'vehicle') or contains(@class,'result') or contains(@class,'listing')]"
        )

        log_widget.write_line(f"[📦] Cards encontrados: {len(car_cards)}")

        for card in car_cards[:int(limite_resultados)]:
            try:
                texto = card.text.strip()
                if len(texto) < 20:
                    continue

                # Tenta extrair modelo e preço de forma simples
                linhas = [l.strip() for l in texto.split("\n") if l.strip()]
                modelo = linhas[0] if linhas else "N/A"

                preco = "N/A"
                for l in linhas:
                    if any(c in l for c in ["€", "$", "R$", "£"]):
                        preco = l
                        break

                dados_carros.append({
                    "Modelo": modelo[:80],
                    "Locadora": "DiscoverCars",
                    "Preco_Total": preco
                })
                log_widget.write_line(f"      → {modelo[:50]} | {preco}")
            except:
                continue

    except Exception as e:
        log_widget.write_line(f"[❌] Erro: {type(e).__name__} - {str(e)[:200]}")
        try:
            driver.save_screenshot("erro_tela.png")
            log_widget.write_line("[📸] Print salvo")
            # Salva também o HTML para debug
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            log_widget.write_line("[📄] HTML salvo em debug_page.html")
        except:
            pass
    finally:
        try:
            driver.quit()
        except:
            pass

    if dados_carros:
        nome = f"discovercars_{destino.lower().replace(' ', '_')}.csv"
        with open(nome, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Modelo", "Locadora", "Preco_Total"])
            writer.writeheader()
            writer.writerows(dados_carros)
        log_widget.write_line(f"[🎉] SUCESSO! {nome}")
    else:
        log_widget.write_line("[⚠️] Nenhum veículo capturado.")
