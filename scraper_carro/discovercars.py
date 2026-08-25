import time
import csv
import re

from textual.app import App, ComposeResult
from textual.widgets import Header, Input, Button, Label, Log
from textual.containers import Container

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

from selenium_stealth import stealth


# ============================================================
# CONVERTER PREÇO
# Aceita:
# R$1,978.60
# R$1.978,60
# R$ 1978,60
# R$ 1978.60
# ============================================================

def converter_preco(texto):
    try:
        texto = (
            texto
            .replace("R$", "")
            .replace("€", "")
            .replace("£", "")
            .replace("$", "")
            .replace("\xa0", "")
            .replace(" ", "")
            .strip()
        )

        if not texto:
            return None

        # Caso tenha ponto e vírgula
        if "." in texto and "," in texto:

            # Brasileiro: 1.978,60
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "")
                texto = texto.replace(",", ".")

            # Americano: 1,978.60
            else:
                texto = texto.replace(",", "")

        # Só vírgula: 1978,60
        elif "," in texto:
            texto = texto.replace(",", ".")

        # Só ponto:
        # 1978.60 ou 1.978
        elif "." in texto:

            partes = texto.split(".")

            # Se termina com 3 casas, assumimos separador de milhar
            if len(partes[-1]) == 3:
                texto = texto.replace(".", "")

        return float(texto)

    except Exception:
        return None


# ============================================================
# FORMATAR PREÇO PT-BR
# ============================================================

def formatar_preco(valor):
    if valor is None:
        return "R$ N/A"

    try:
        return (
            f"R$ {valor:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    except Exception:
        return "R$ N/A"


# ============================================================
# EXTRAIR UM CARD
# ============================================================

def extrair_card(card):

    # ========================================================
    # MODELO
    # ========================================================

    modelo = ""

    elementos_modelo = card.find_elements(
        By.CSS_SELECTOR,
        ".CarTitle-Name"
    )

    for elemento in elementos_modelo:
        texto = (
            elemento.text
            or elemento.get_attribute("textContent")
            or ""
        ).strip()

        if texto:
            modelo = texto
            break

    if not modelo:
        raise ValueError("Modelo vazio")

    # ========================================================
    # PREÇO
    # ========================================================

    preco_original = ""
    preco_numero = None

    elementos_preco = card.find_elements(
        By.CSS_SELECTOR,
        ".SearchCar-Price"
    )

    for elemento in elementos_preco:

        texto = (
            elemento.text
            or elemento.get_attribute("textContent")
            or ""
        ).strip()

        if not texto:
            continue

        valor = converter_preco(
            texto
        )

        if valor is not None and valor > 0:
            preco_original = texto
            preco_numero = valor
            break

    # ========================================================
    # FALLBACK DO PREÇO
    # Busca R$ diretamente no texto inteiro do card
    # ========================================================

    if preco_numero is None:

        texto_card_completo = (
            card.get_attribute("textContent")
            or ""
        )

        encontrados = re.findall(
            r"R\$\s*[\d.,]+",
            texto_card_completo
        )

        for encontrado in encontrados:

            valor = converter_preco(
                encontrado
            )

            if valor is not None and valor > 0:
                preco_original = encontrado
                preco_numero = valor
                break

    if preco_numero is None:
        raise ValueError(
            f"Preço não encontrado em {modelo}"
        )

    # ========================================================
    # LOCADORA
    # ========================================================

    locadora = "N/A"

    try:

        imagens = card.find_elements(
            By.CSS_SELECTOR,
            "[class*='SupplierInfo'] img"
        )

        for imagem in imagens:

            alt = (
                imagem.get_attribute("alt")
                or ""
            ).strip()

            title = (
                imagem.get_attribute("title")
                or ""
            ).strip()

            if alt:
                locadora = alt
                break

            if title:
                locadora = title
                break

    except Exception:
        pass

    # ========================================================
    # NOTA
    # ========================================================

    nota = "N/A"

    try:

        texto_card = (
            card.text
            or card.get_attribute("textContent")
            or ""
        )

        linhas = [
            linha.strip()
            for linha in texto_card.split("\n")
            if linha.strip()
        ]

        for linha in linhas:
            try:
                numero = float(
                    linha.replace(",", ".")
                )

                if 5.0 <= numero <= 10.0:
                    nota = linha
                    break

            except Exception:
                continue

    except Exception:
        pass

    # ========================================================
    # AVALIAÇÕES
    # ========================================================

    avaliacoes = "N/A"

    try:

        elemento = card.find_element(
            By.CSS_SELECTOR,
            ".SupplierInfo-SupplierReviews"
        )

        avaliacoes = (
            elemento.text
            or elemento.get_attribute("textContent")
            or "N/A"
        ).strip()

    except Exception:
        pass

    # ========================================================
    # CATEGORIA
    # ========================================================

    categoria = "N/A"

    try:

        elemento = card.find_element(
            By.CSS_SELECTOR,
            ".CarTitle-Similar"
        )

        categoria = (
            elemento.text
            or elemento.get_attribute("textContent")
            or "N/A"
        ).strip()

    except Exception:
        pass

    # ========================================================
    # LINK
    # ========================================================

    link = ""

    try:

        elemento = card.find_element(
            By.CSS_SELECTOR,
            "a[href*='/offer/']"
        )

        link = (
            elemento.get_attribute("href")
            or ""
        )

    except Exception:
        pass

    return {
        "Modelo": modelo,
        "Categoria": categoria,
        "Locadora": locadora,
        "PrecoOriginal": preco_original,
        "PrecoNumero": preco_numero,
        "Nota": nota,
        "Avaliacoes": avaliacoes,
        "Link": link
    }


# ============================================================
# SCRAPER
# ============================================================

def executar_scraper(
    destino,
    data_retirada,
    data_devolucao,
    limite_resultados,
    log_widget
):

    driver = None

    try:

        # ====================================================
        # CHROMIUM
        # ====================================================

        log_widget.write_line(
            "[⚙️] Inicializando Chromium..."
        )

        options = webdriver.ChromeOptions()

        options.binary_location = (
            "/usr/sbin/chromium"
        )

        options.add_argument(
            "--start-maximized"
        )

        options.add_argument(
            "--window-size=1920,1080"
        )

        options.add_argument(
            "--lang=en-US"
        )

        options.add_argument(
            "--disable-blink-features=AutomationControlled"
        )

        options.add_experimental_option(
            "excludeSwitches",
            ["enable-automation"]
        )

        options.add_experimental_option(
            "useAutomationExtension",
            False
        )

        driver = webdriver.Chrome(
            options=options
        )

        stealth(
            driver,
            languages=[
                "en-US",
                "en"
            ],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True
        )

        wait = WebDriverWait(
            driver,
            30
        )

        # ====================================================
        # ABRIR SITE
        # ====================================================

        log_widget.write_line(
            "[🌐] Acessando DiscoverCars..."
        )

        driver.get(
            "https://www.discovercars.com/"
        )

        time.sleep(3)

        # ====================================================
        # COOKIES
        # ====================================================

        try:

            cookie = driver.find_element(
                By.XPATH,
                "//button["
                "contains(., 'Accept') "
                "or contains(., 'Agree') "
                "or contains(., 'Aceitar')"
                "]"
            )

            driver.execute_script(
                "arguments[0].click();",
                cookie
            )

            time.sleep(1)

        except Exception:
            pass

        # ====================================================
        # DESTINO
        # ====================================================

        log_widget.write_line(
            f"[📍] Destino: {destino}"
        )

        campo_destino = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    "input.Autocomplete-EnterLocation"
                    "[name='PickupLocation']"
                )
            )
        )

        driver.execute_script(
            "arguments[0].scrollIntoView("
            "{block:'center'}"
            ");",
            campo_destino
        )

        time.sleep(0.5)

        try:
            campo_destino.click()

        except Exception:
            driver.execute_script(
                "arguments[0].click();",
                campo_destino
            )

        campo_destino.send_keys(
            Keys.CONTROL + "a"
        )

        campo_destino.send_keys(
            Keys.BACKSPACE
        )

        for letra in destino:
            campo_destino.send_keys(
                letra
            )

            time.sleep(0.10)

        log_widget.write_line(
            "[⏳] Aguardando sugestões..."
        )

        time.sleep(3)

        # ====================================================
        # SUGESTÃO
        # ====================================================

        sugestao_escolhida = False

        try:

            sugestoes = driver.find_elements(
                By.XPATH,
                "//li[@role='option'] "
                "| "
                "//div[contains(@class,'autocomplete')]//li "
                "| "
                "//div[contains(@class,'suggestion')]//li"
            )

            if sugestoes:

                driver.execute_script(
                    "arguments[0].click();",
                    sugestoes[0]
                )

                sugestao_escolhida = True

                log_widget.write_line(
                    "[✅] Destino selecionado"
                )

        except Exception:
            pass

        if not sugestao_escolhida:

            log_widget.write_line(
                "[⚠️] Dropdown direto falhou, "
                "tentando teclado..."
            )

            campo_destino.send_keys(
                Keys.ARROW_DOWN
            )

            time.sleep(0.5)

            campo_destino.send_keys(
                Keys.ENTER
            )

        time.sleep(1.5)

        # ====================================================
        # SEARCH
        # ====================================================

        log_widget.write_line(
            "[🔍] Clicando Search now..."
        )

        try:

            botao = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[contains(.,'Search now')]"
                    )
                )
            )

            driver.execute_script(
                "arguments[0].click();",
                botao
            )

        except Exception:
            campo_destino.send_keys(
                Keys.ENTER
            )

        log_widget.write_line(
            "[⏳] Aguardando página de resultados..."
        )

        # ====================================================
        # AGUARDAR /SEARCH/
        # ====================================================

        try:

            wait.until(
                lambda d:
                "/search/" in d.current_url
            )

        except Exception:
            pass

        log_widget.write_line(
            "[🌐] Página de resultados aberta"
        )

        # ====================================================
        # PRIMEIRO CARD
        # ====================================================

        wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    ".SearchList-Card"
                )
            )
        )

        log_widget.write_line(
            "[✅] Resultados carregados"
        )

        time.sleep(2)

        # ====================================================
        # ORDENAR POR PREÇO
        # ====================================================

        log_widget.write_line(
            "[💰] Ordenando por menor preço..."
        )

        try:

            select_element = wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "select[aria-label='Sort by']"
                    )
                )
            )

            seletor = Select(
                select_element
            )

            seletor.select_by_value(
                "Price"
            )

            log_widget.write_line(
                "[✅] Ordenação Price selecionada"
            )

            time.sleep(5)

            primeiro_card = wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        ".SearchList-Card"
                    )
                )
            )

            driver.execute_script(
                "arguments[0].scrollIntoView("
                "{block:'start'}"
                ");",
                primeiro_card
            )

            time.sleep(2)

        except Exception as e:

            log_widget.write_line(
                "[⚠️] Ordenação automática falhou:"
            )

            log_widget.write_line(
                f"    {str(e)[:150]}"
            )

        # ====================================================
        # LIMITE
        # ====================================================

        try:

            limite = int(
                limite_resultados
            )

        except Exception:
            limite = 10

        if limite < 1:
            limite = 10

        # ====================================================
        # COLETAR CARDS
        # ====================================================

        log_widget.write_line(
            f"[🚗] Capturando os {limite} "
            "primeiros preços..."
        )

        carros = {}

        tentativas_sem_novo = 0
        ultimo_total = 0

        for ciclo in range(40):

            cards = driver.find_elements(
                By.CSS_SELECTOR,
                ".SearchList-Card"
            )

            log_widget.write_line(
                f"[📦] Cards visíveis: {len(cards)}"
            )

            ultimo_card = None

            for card in cards:

                ultimo_card = card

                try:

                    carro = extrair_card(
                        card
                    )

                    if carro["Link"]:
                        chave = carro["Link"]

                    else:
                        chave = (
                            carro["Modelo"]
                            + "|"
                            + carro["PrecoOriginal"]
                        )

                    if chave not in carros:

                        carros[chave] = carro

                        log_widget.write_line(
                            f"  [+] "
                            f"{carro['Modelo']} | "
                            f"{formatar_preco(carro['PrecoNumero'])}"
                        )

                except Exception:
                    continue

            if len(carros) >= limite:
                break

            if len(carros) == ultimo_total:
                tentativas_sem_novo += 1

            else:
                tentativas_sem_novo = 0
                ultimo_total = len(carros)

            if tentativas_sem_novo >= 5:

                log_widget.write_line(
                    "[⚠️] Lista parou de fornecer novos cards."
                )

                break

            if ultimo_card is not None:

                try:

                    driver.execute_script(
                        """
                        arguments[0].scrollIntoView({
                            behavior: 'instant',
                            block: 'end'
                        });
                        """,
                        ultimo_card
                    )

                except Exception:

                    driver.execute_script(
                        "window.scrollBy(0, 500);"
                    )

            else:

                driver.execute_script(
                    "window.scrollBy(0, 400);"
                )

            time.sleep(1)

        # ====================================================
        # RESULTADOS
        # ====================================================

        resultados = list(
            carros.values()
        )

        resultados.sort(
            key=lambda x:
            x["PrecoNumero"]
        )

        resultados = resultados[:limite]

        log_widget.write_line("")

        log_widget.write_line(
            "================================"
        )

        if not resultados:

            log_widget.write_line(
                "[❌] Nenhuma oferta capturada"
            )

            driver.save_screenshot(
                "erro_sem_carros.png"
            )

            return

        log_widget.write_line(
            f"[🏆] TOP {len(resultados)} "
            "MENORES PREÇOS"
        )

        log_widget.write_line(
            "================================"
        )

        for numero, carro in enumerate(
            resultados,
            1
        ):

            preco_formatado = formatar_preco(
                carro["PrecoNumero"]
            )

            log_widget.write_line(
                f"{numero}. "
                f"{carro['Modelo']} | "
                f"{preco_formatado}"
            )

            log_widget.write_line(
                f"    Locadora: "
                f"{carro['Locadora']}"
            )

            log_widget.write_line(
                f"    Nota: "
                f"{carro['Nota']}"
            )

        # ====================================================
        # CSV
        # ====================================================

        nome_destino = (
            destino
            .lower()
            .replace(" ", "_")
            .replace("/", "_")
        )

        nome_csv = (
            f"discovercars_{nome_destino}.csv"
        )

        with open(
            nome_csv,
            "w",
            newline="",
            encoding="utf-8"
        ) as arquivo:

            campos = [
                "Modelo",
                "Categoria",
                "Locadora",
                "Preco",
                "Nota",
                "Avaliacoes",
                "Link"
            ]

            writer = csv.DictWriter(
                arquivo,
                fieldnames=campos
            )

            writer.writeheader()

            for carro in resultados:

                writer.writerow({
                    "Modelo":
                        carro["Modelo"],

                    "Categoria":
                        carro["Categoria"],

                    "Locadora":
                        carro["Locadora"],

                    "Preco":
                        formatar_preco(
                            carro["PrecoNumero"]
                        ),

                    "Nota":
                        carro["Nota"],

                    "Avaliacoes":
                        carro["Avaliacoes"],

                    "Link":
                        carro["Link"]
                })

        log_widget.write_line("")

        log_widget.write_line(
            f"[💾] CSV salvo: {nome_csv}"
        )

        log_widget.write_line(
            "[🎉] CONCLUÍDO!"
        )

        try:

            driver.save_screenshot(
                "resultado_final.png"
            )

        except Exception:
            pass

    # ========================================================
    # ERRO
    # ========================================================

    except Exception as e:

        log_widget.write_line("")

        log_widget.write_line(
            f"[❌] {type(e).__name__}"
        )

        log_widget.write_line(
            f"[❌] {str(e)[:300]}"
        )

        if driver:

            try:

                driver.save_screenshot(
                    "erro_discovercars.png"
                )

                with open(
                    "erro_discovercars.html",
                    "w",
                    encoding="utf-8"
                ) as arquivo:

                    arquivo.write(
                        driver.page_source
                    )

                log_widget.write_line(
                    "[📸] Arquivos de diagnóstico salvos."
                )

            except Exception:
                pass

    finally:

        if driver:

            time.sleep(2)

            try:
                driver.quit()

            except Exception:
                pass


# ============================================================
# INTERFACE
# ============================================================

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
                "Destino:"
            )

            yield Input(
                placeholder="Ibiza Airport",
                id="destino"
            )

            yield Label(
                "Data Retirada (AAAA-MM-DD):"
            )

            yield Input(
                placeholder="2026-08-14",
                id="retirada"
            )

            yield Label(
                "Data Devolução (AAAA-MM-DD):"
            )

            yield Input(
                placeholder="2026-08-22",
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
                "[🚨] Digite o destino!"
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
