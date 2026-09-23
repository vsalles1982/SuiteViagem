import os
import re
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import box

console = Console()

PASTA_FEEDS = os.path.expanduser("~/feeds_voos")
os.makedirs(PASTA_FEEDS, exist_ok=True)

ROTAS_PADRAO = {
    "1": ("Rio x SP", "RIO", "SAO"),
    "2": ("Rio x NYC", "RIO", "NYC"),
    "3": ("Rio x Paris", "RIO", "PAR"),
    "4": ("Rio x Alemanha", "RIO", "FRA"),
}

PERIODOS = {
    "1": ("1 semana", 7, 1),
    "2": ("1 mês", 30, 3),
    "3": ("2 meses", 60, 4),
    "4": ("3 meses", 90, 5),
    "5": ("6 meses", 180, 7),
    "6": ("1 ano", 365, 10),
}

DURACOES_VIAGEM = {
    "1": ("3 dias", 3),
    "2": ("5 dias", 5),
    "3": ("7 dias", 7),
    "4": ("10 dias", 10),
    "5": ("14 dias", 14),
}

def mostrar_banner():
    console.print(Panel.fit(
        "[bold cyan]✈  Google Flights Monitor - TUI[/bold cyan]\n"
        "[dim]Melhor preço • Ida ou Ida e Volta[/dim]",
        border_style="cyan",
        padding=(1, 4)
    ))

def escolher_tipo_viagem():
    console.print("\n[bold]Tipo de viagem:[/bold]\n")

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column("Opção", style="bold cyan", width=6)
    table.add_column("Tipo")
    table.add_row("[1]", "Só ida")
    table.add_row("[2]", "Ida e volta")
    console.print(table)

    escolha = Prompt.ask("\nDigite o número", choices=["1", "2"], default="1")
    return escolha == "2"  # True = ida e volta

def escolher_duracao():
    console.print("\n[bold]Duração da viagem (ida e volta):[/bold]\n")

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column("Opção", style="bold cyan", width=6)
    table.add_column("Duração")

    for k, (nome, _) in DURACOES_VIAGEM.items():
        table.add_row(f"[{k}]", nome)

    console.print(table)

    escolha = Prompt.ask("\nDigite o número", choices=list(DURACOES_VIAGEM.keys()), default="3")
    nome, dias = DURACOES_VIAGEM[escolha]
    console.print(f"[green]✓ Duração: {nome}[/green]")
    return dias, nome

def escolher_periodo():
    console.print("\n[bold]Escolha o período de busca:[/bold]\n")

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column("Opção", style="bold cyan", width=6)
    table.add_column("Período")

    for k, (nome, dias, _) in PERIODOS.items():
        table.add_row(f"[{k}]", nome)

    console.print(table)

    escolha = Prompt.ask("\nDigite o número", choices=list(PERIODOS.keys()), default="3")
    nome, dias, passo = PERIODOS[escolha]
    console.print(f"[green]✓ Período selecionado: {nome} ({dias} dias)[/green]")
    return dias, passo, nome

def escolher_destinos():
    console.print("\n[bold]Escolha os destinos (pode marcar vários):[/bold]\n")

    table = Table(box=box.ROUNDED, show_header=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Rota", style="bold")
    table.add_column("Códigos")

    for k, (nome, o, d) in ROTAS_PADRAO.items():
        table.add_row(k, nome, f"{o} → {d}")

    console.print(table)
    console.print("\n[dim]Digite os números separados por espaço (ex: 1 3 4)[/dim]")
    console.print("[dim]Ou digite 'c' para adicionar um destino personalizado[/dim]")

    while True:
        entrada = Prompt.ask("\nSeleção").strip().lower()

        if entrada == "c":
            return adicionar_destino_custom()

        try:
            numeros = entrada.split()
            selecionados = []
            for n in numeros:
                if n in ROTAS_PADRAO:
                    selecionados.append(ROTAS_PADRAO[n])

            if selecionados:
                console.print("\n[green]✓ Destinos selecionados:[/green]")
                for nome, o, d in selecionados:
                    console.print(f"  • {nome} ({o} → {d})")
                return selecionados
            else:
                console.print("[red]Nenhuma opção válida. Tente novamente.[/red]")
        except:
            console.print("[red]Entrada inválida.[/red]")

def adicionar_destino_custom():
    console.print("\n[bold cyan]Adicionar destino personalizado[/bold cyan]")
    origem = Prompt.ask("Código de origem (ex: RIO, GRU, GIG)").upper().strip()
    destino = Prompt.ask("Código de destino (ex: LIS, MIA, MAD)").upper().strip()
    nome = Prompt.ask("Nome da rota (ex: Rio x Lisboa)", default=f"{origem} x {destino}")

    console.print(f"\n[green]✓ Adicionado: {nome} ({origem} → {destino})[/green]")
    return [(nome, origem, destino)]

def gerar_datas(dias_frente, passo):
    datas = []
    hoje = datetime.now().date()
    inicio = 5
    for i in range(inicio, dias_frente + 1, passo):
        data = hoje + timedelta(days=i)
        datas.append(data.strftime("%Y-%m-%d"))
    return datas

def montar_url(origem, destino, data_ida, ida_volta=False, duracao=7):
    if ida_volta:
        data_volta = (datetime.strptime(data_ida, "%Y-%m-%d") + timedelta(days=duracao)).strftime("%Y-%m-%d")
        q = f"Flights from {origem} to {destino} on {data_ida} through {data_volta}"
    else:
        q = f"Flights from {origem} to {destino} on {data_ida} oneway"

    from urllib.parse import quote
    return f"https://www.google.com/travel/flights?q={quote(q)}&curr=BRL&hl=pt-BR"

def executar_raspagem(page, url):
    page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9"
    })

    page.goto(url, wait_until="domcontentloaded", timeout=55000)

    try:
        botao = page.locator('button:has-text("Aceitar tudo"), button:has-text("Concordo"), button:has-text("Accept all")')
        if botao.first.is_visible(timeout=4000):
            botao.first.click()
            time.sleep(1.2)
    except:
        pass

    page.evaluate("window.scrollTo(0, 450)")
    time.sleep(2.5)

    try:
        page.wait_for_selector("span:has-text('R$'), div:has-text('R$')", timeout=25000)
    except:
        pass

    time.sleep(1.5)

    conteudo = page.locator("body").inner_text()
    precos_raw = re.findall(r"R\$\s*([\d\.]+)", conteudo)

    precos_validos = []
    for p in precos_raw:
        valor = int(p.replace(".", ""))
        if 180 <= valor <= 30000:  # um pouco mais alto para ida e volta
            precos_validos.append(valor)

    return min(precos_validos) if precos_validos else None

def raspar_melhor_preco(nome, origem, destino, dias, passo, ida_volta=False, duracao=7):
    datas = gerar_datas(dias, passo)
    melhor_preco = None
    melhor_data = None

    tipo = "Ida e volta" if ida_volta else "Só ida"
    console.print(f"\n[bold]→ {nome}[/bold]  [dim]({tipo} • {len(datas)} datas)[/dim]")

    with console.status("[cyan]Buscando preços...[/cyan]", spinner="dots"):
        for data in datas:
            url = montar_url(origem, destino, data, ida_volta, duracao)
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                    )
                    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="pt-BR")
                    page = context.new_page()
                    preco = executar_raspagem(page, url)
                    browser.close()

                    if preco is not None:
                        if melhor_preco is None or preco < melhor_preco:
                            melhor_preco = preco
                            melhor_data = data
            except Exception:
                pass

            time.sleep(1.3)

    if melhor_preco:
        data_fmt = datetime.strptime(melhor_data, "%Y-%m-%d").strftime("%d/%m/%Y")
        if ida_volta:
            data_volta = (datetime.strptime(melhor_data, "%Y-%m-%d") + timedelta(days=duracao)).strftime("%d/%m")
            resultado = f"A partir de R$ {melhor_preco:,}".replace(",", ".") + f" ({data_fmt} → {data_volta})"
        else:
            resultado = f"A partir de R$ {melhor_preco:,}".replace(",", ".") + f" ({data_fmt})"

        console.print(f"  [green]Melhor: {resultado}[/green]")
        return resultado
    else:
        console.print("  [red]Preço não localizado[/red]")
        return "Preço não localizado"

def criar_rss_local(nome_rota, origem, destino, resultado_preco, periodo_nome, ida_volta, duracao_nome=None):
    nome_arquivo = f"{nome_rota.lower().replace(' ', '_')}.xml"
    caminho = os.path.join(PASTA_FEEDS, nome_arquivo)
    data_atual = datetime.now().strftime("%a, %d %b %Y %H:%M:%S -0300")

    link = f"https://www.google.com/travel/flights?q=Flights%20from%20{origem}%20to%20{destino}&curr=BRL&hl=pt-BR"

    tipo = f"Ida e volta ({duracao_nome})" if ida_volta else "Só ida"

    rss = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
    <title>Google Flights: {nome_rota}</title>
    <link>{link}</link>
    <description>Melhor preço - {periodo_nome} - {tipo}</description>
    <lastBuildDate>{data_atual}</lastBuildDate>
    <item>
        <title>{nome_rota} → {resultado_preco}</title>
        <link>{link}</link>
        <pubDate>{data_atual}</pubDate>
        <guid isPermaLink="false">{nome_rota}_{datetime.now().strftime('%Y%m%d%H%M%S')}</guid>
        <description>Melhor preço encontrado no período de {periodo_nome} ({tipo}). Verificação: {data_atual}</description>
    </item>
</channel>
</rss>"""

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(rss)

# ===================== MAIN =====================
if __name__ == "__main__":
    console.clear()
    mostrar_banner()

    # 1. Tipo de viagem
    ida_volta = escolher_tipo_viagem()

    duracao = 7
    duracao_nome = None
    if ida_volta:
        duracao, duracao_nome = escolher_duracao()

    # 2. Período
    dias, passo, periodo_nome = escolher_periodo()

    # 3. Destinos
    destinos = escolher_destinos()

    console.print(f"\n[bold yellow]Iniciando busca...[/bold yellow]")
    if ida_volta:
        console.print(f"[dim]Tipo: Ida e volta • Duração: {duracao_nome} • Período: {periodo_nome}[/dim]\n")
    else:
        console.print(f"[dim]Tipo: Só ida • Período: {periodo_nome}[/dim]\n")

    for nome, origem, destino in destinos:
        resultado = raspar_melhor_preco(
            nome, origem, destino, dias, passo,
            ida_volta=ida_volta, duracao=duracao
        )
        criar_rss_local(nome, origem, destino, resultado, periodo_nome, ida_volta, duracao_nome)
        time.sleep(2)

    console.print(Panel.fit(
        "[bold green]✓ Varredura concluída![/bold green]\n"
        f"Feeds salvos em: {PASTA_FEEDS}",
        border_style="green"
    ))
