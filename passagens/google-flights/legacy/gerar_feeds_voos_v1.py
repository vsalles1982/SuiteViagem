import os
import re
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

PASTA_FEEDS = os.path.expanduser("~/feeds_voos")
os.makedirs(PASTA_FEEDS, exist_ok=True)

# Gera uma data daqui a 30 dias (mais estável que "sem data")
data_futura = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

ROTAS = {
    "Rio x SP": f"https://www.google.com/travel/flights?q=Flights%20from%20RIO%20to%20SAO%20on%20{data_futura}%20oneway&curr=BRL&hl=pt-BR",
    "Rio x NYC": f"https://www.google.com/travel/flights?q=Flights%20from%20RIO%20to%20NYC%20on%20{data_futura}%20oneway&curr=BRL&hl=pt-BR",
    "Rio x Paris": f"https://www.google.com/travel/flights?q=Flights%20from%20RIO%20to%20PAR%20on%20{data_futura}%20oneway&curr=BRL&hl=pt-BR",
    "Rio x Alemanha": f"https://www.google.com/travel/flights?q=Flights%20from%20RIO%20to%20FRA%20on%20{data_futura}%20oneway&curr=BRL&hl=pt-BR"
}

def executar_raspagem(page, url):
    page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9"
    })

    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    # Aceitar cookies se aparecer
    try:
        botao = page.locator('button:has-text("Aceitar tudo"), button:has-text("Concordo"), button:has-text("Accept all")')
        if botao.first.is_visible(timeout=5000):
            botao.first.click()
            time.sleep(1.5)
    except:
        pass

    # Rola um pouco e espera os preços de voo aparecerem
    page.evaluate("window.scrollTo(0, 400)")
    time.sleep(3)

    # Espera por qualquer elemento que contenha "R$" (mais tolerante)
    try:
        page.wait_for_selector("span:has-text('R$'), div:has-text('R$')", timeout=30000)
    except:
        pass

    time.sleep(2)  # tempo extra pro JS terminar de carregar

    conteudo = page.locator("body").inner_text()

    # Pega todos os preços no formato R$ 1.234 ou R$ 1234
    precos_raw = re.findall(r"R\$\s*([\d\.]+)", conteudo)

    precos_validos = []
    for p in precos_raw:
        # Remove pontos de milhar
        valor = int(p.replace(".", ""))
        # Filtra preços absurdamente baixos (quase nunca é passagem)
        if 150 <= valor <= 15000:
            precos_validos.append(valor)

    if precos_validos:
        menor = min(precos_validos)
        return f"A partir de R$ {menor:,}".replace(",", ".")

    return "Preço não localizado"


def raspar_google_flights_com_retry(url):
    for tentativa in range(3):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )
                context = browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    locale="pt-BR"
                )
                page = context.new_page()
                resultado = executar_raspagem(page, url)
                browser.close()
                return resultado
        except Exception as e:
            erro = str(e)
            if "Timeout" in erro:
                erro = "Timeout no carregamento"
            time.sleep(4)

    return f"Erro na raspagem: {erro}"


def criar_rss_local(nome_rota, link_rota, resultado_preco):
    nome_arquivo = f"{nome_rota.lower().replace(' ', '_')}.xml"
    caminho = os.path.join(PASTA_FEEDS, nome_arquivo)
    data_atual = datetime.now().strftime("%a, %d %b %Y %H:%M:%S -0300")

    rss = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
    <title>Google Flights: {nome_rota}</title>
    <link>{link_rota}</link>
    <description>Monitoramento de passagens</description>
    <lastBuildDate>{data_atual}</lastBuildDate>
    <item>
        <title>{nome_rota} → {resultado_preco}</title>
        <link>{link_rota}</link>
        <pubDate>{data_atual}</pubDate>
        <guid isPermaLink="false">{nome_rota}_{datetime.now().strftime('%Y%m%d%H%M')}</guid>
        <description>Última verificação: {data_atual}</description>
    </item>
</channel>
</rss>"""

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"Feed gerado: {caminho}")


if __name__ == "__main__":
    print("Iniciando varredura no Google Flights...\n")
    for rota, url in ROTAS.items():
        print(f"→ Verificando {rota}...")
        preco = raspar_google_flights_com_retry(url)
        print(f"  Resultado: {preco}")
        criar_rss_local(rota, url, preco)
        time.sleep(2)  # pequena pausa entre rotas
    print("\nVarredura concluída!")
