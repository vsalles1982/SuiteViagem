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
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    consentimento = page.get_by_role(
        "button", name=re.compile(r"Aceitar tudo|Accept all|Concordo", re.I)
    )
    if consentimento.count() and consentimento.first.is_visible():
        consentimento.first.click()

    aba = page.get_by_role(
        "tab", name=re.compile(r"Menores preços|Cheapest", re.I)
    ).first
    aba.wait_for(state="visible", timeout=30000)

    # Aguardar cartões antes de mudar de aba.
    page.locator("li").filter(
        has_text=re.compile(r"R\$")
    ).first.wait_for(state="visible", timeout=45000)

    aba.click(timeout=15000)

    limite = time.monotonic() + 75
    anterior = None
    estavel_desde = None

    while time.monotonic() < limite:
        page.wait_for_timeout(1000)

        corpo = page.locator("body").inner_text()
        if "Algo deu errado" in corpo:
            raise RuntimeError("Google Flights informou erro na consulta.")

        # Não aceitar resultados de outra aba.
        if aba.get_attribute("aria-selected") != "true":
            anterior = None
            estavel_desde = None
            continue

        cartoes = []
        precos = []

        for item in page.locator("li").all():
            if not item.is_visible():
                continue

            texto = item.inner_text()

            # Exigir horário e informação de escalas no mesmo cartão.
            if not re.search(r"\b\d{1,2}:\d{2}\b", texto):
                continue
            if not re.search(
                r"Sem escalas|\b\d+\s+paradas?\b|\b\d+\s+escalas?\b",
                texto, re.I
            ):
                continue

            valores = re.findall(
                r"R\$\s*([0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2})?)",
                texto
            )
            # Cartão ambíguo precisa de análise, não de um palpite.
            if len(valores) != 1:
                continue

            valor = float(valores[0].replace(".", "").replace(",", "."))
            if valor <= 0:
                continue

            cartoes.append(texto)
            precos.append(valor)

        assinatura = tuple(cartoes)

        if not assinatura:
            anterior = None
            estavel_desde = None
            continue

        if assinatura != anterior:
            anterior = assinatura
            estavel_desde = time.monotonic()
            continue

        # Janela de estabilidade; não usar o preço inicial do cabeçalho.
        if time.monotonic() - estavel_desde >= 8:
            menor = min(precos)
            console.print(
                f"  [dim]{len(precos)} cartões estáveis; "
                f"menor preço listado: R$ {menor:.2f}[/dim]"
            )
            return int(menor) if menor.is_integer() else menor

    raise RuntimeError(
        "Não foi possível confirmar cartões estáveis na aba Menores preços."
    )


def formatar_preco(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def raspar_melhor_preco(nome, origem, destino, dias, passo, ida_volta=False, duracao=7):
    """Consulta cada data com até duas tentativas e informa a cobertura."""
    datas = gerar_datas(dias, passo)
    resultado = {
        "preco": None, "data": None, "url": None,
        "datas": datas, "sucessos": [], "falhas": [],
        "passo": passo, "ida_volta": ida_volta, "duracao": duracao,
    }
    tipo = "Ida e volta" if ida_volta else "Só ida"
    console.print(f"\n→ {nome} ({tipo} • {len(datas)} datas)", markup=False)
    console.print(
        f"Busca a partir de daqui a 5 dias; intervalo: {passo} dia(s).",
        markup=False,
    )

    for indice, data in enumerate(datas, 1):
        url = montar_url(origem, destino, data, ida_volta, duracao)
        erros = []

        for tentativa in (1, 2):
            console.print(
                f"  [{indice}/{len(datas)}] {data} — tentativa {tentativa}/2",
                markup=False,
            )
            try:
                with console.status(
                    f"[cyan]Consultando {data}; aguardando cartões estáveis…[/cyan]",
                    spinner="dots",
                ):
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        try:
                            context = browser.new_context(
                                viewport={"width": 1280, "height": 900},
                                locale="pt-BR",
                            )
                            page = context.new_page()
                            preco = executar_raspagem(page, url)
                            if preco is None or preco <= 0:
                                raise RuntimeError("Nenhum preço válido nos cartões.")
                        finally:
                            browser.close()

                resultado["sucessos"].append({"data": data, "preco": preco})
                if resultado["preco"] is None or preco < resultado["preco"]:
                    resultado.update(preco=preco, data=data, url=url)

                console.print(
                    f"  ✓ {data}: {formatar_preco(preco)}",
                    markup=False,
                )
                break

            except Exception as erro:
                erros.append(str(erro))
                console.print(
                    f"  Tentativa {tentativa} falhou: {erro}",
                    markup=False,
                )
                if tentativa == 1:
                    with console.status(
                        "[yellow]Aguardando 5 segundos antes da última tentativa…[/yellow]",
                        spinner="dots",
                    ):
                        time.sleep(5)
                else:
                    resultado["falhas"].append({
                        "data": data,
                        "erro": str(erro),
                        "tentativas": erros,
                    })

        if indice < len(datas):
            time.sleep(1.3)

    console.print(
        f"  Datas com preço: {len(resultado['sucessos'])}/{len(datas)}; "
        f"falhas: {len(resultado['falhas'])}.",
        markup=False,
    )
    if resultado["preco"] is not None:
        console.print("  " + descrever_resultado(resultado), markup=False)
        if resultado["falhas"]:
            console.print(
                "  Consulta parcial: o menor preço considera apenas "
                "as datas com resultado.",
                style="yellow",
            )
    else:
        console.print("  Nenhum preço confirmado.", style="yellow")
    return resultado


def descrever_resultado(resultado):
    ida = datetime.strptime(resultado["data"], "%Y-%m-%d")
    datas = ida.strftime("%d/%m/%Y")
    if resultado["ida_volta"]:
        volta = ida + timedelta(days=resultado["duracao"])
        datas += " → " + volta.strftime("%d/%m/%Y")
    return f"Menor preço consultado: {formatar_preco(resultado['preco'])} ({datas})"



def formatar_artigo_html(titulo, descricao, link, atualizado):
    from html import escape
    import re
    import textwrap

    def extrair(padrao, padrao_alternativo="Não informado"):
        encontrado = re.search(padrao, descricao)
        return encontrado.group(1).strip() if encontrado else padrao_alternativo

    blocos = []

    def grupo(nome, linhas):
        bloco = ["  " + nome]
        for linha in linhas:
            for parte in textwrap.wrap(str(linha), width=54) or [""]:
                bloco.append("  " + parte)
        blocos.append("\n".join(linha.ljust(58) for linha in bloco))

    preco = re.search(r"R\$\s*[0-9.,]+", titulo)
    datas = re.search(r"\((\d{2}/\d{2}/\d{4}[^)]*)\)", titulo)
    parcial = "consulta parcial" in (titulo + descricao).lower()
    tipo = "Ida e volta" if "Ida e volta" in descricao else "Só ida"

    grupo("CONSULTA", [
        "Status: " + ("CONSULTA PARCIAL" if parcial else "Datas programadas consultadas"),
        "Atualizado: " + atualizado,
    ])

    grupo("PREÇO E DATA", [
        preco.group(0) if preco else "Preço não informado",
        datas.group(1) if datas else "Data não informada",
        tipo,
        "Menor preço entre os resultados consultados.",
    ])

    grupo("COBERTURA DA BUSCA", [
        "Datas com preço: " + extrair(r"Datas com preço: ([0-9]+/[0-9]+)"),
        "Falhas: " + extrair(r"Falhas: ([0-9]+)"),
        "Datas com falha: " + extrair(r"Datas com falha: ([^.]+)", "Nenhuma"),
        "Busca iniciada em: " + extrair(r"Busca iniciada em ([0-9-]+)"),
        "Intervalo: " + extrair(r"intervalo de ([0-9]+)") + " dia(s)",
    ])

    grupo("OBSERVAÇÕES", [
        "Considera os cartões reconhecidos nas datas com resultado.",
        "Não representa todas as datas ou todas as ofertas.",
        "Consulte novamente para verificar a disponibilidade.",
    ])

    conteudo = "<pre>" + escape("\n\n".join(blocos)) + "</pre>"
    conteudo += '<p><strong>ABRIR CONSULTA</strong><br>'
    conteudo += '<a href="' + escape(link, quote=True) + '">'
    conteudo += "Google Flights — rota e datas da consulta</a></p>"
    return conteudo


def criar_rss_local(nome_rota, origem, destino, resultado, periodo_nome,
                    ida_volta, duracao_nome=None):
    """Escreve RSS válido de forma atômica; falha de busca preserva o feed."""
    import hashlib
    import tempfile
    import xml.etree.ElementTree as ET
    from email.utils import format_datetime
    from pathlib import Path

    if resultado["preco"] is None:
        return None

    nome_seguro = re.sub(r"[^\w-]+", "_", nome_rota.lower()).strip("_") or "rota"
    pasta = Path(PASTA_FEEDS)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{nome_seguro}.xml"
    agora = datetime.now().astimezone()
    data_rss = format_datetime(agora)
    tipo = f"Ida e volta ({duracao_nome})" if ida_volta else "Só ida"
    parcial = bool(resultado["falhas"])
    cobertura = (f"Datas com preço: {len(resultado['sucessos'])}/"
                 f"{len(resultado['datas'])}. Falhas: {len(resultado['falhas'])}.")
    descricao = (
        f"{origem} → {destino}. {periodo_nome}; {tipo}. {cobertura} "
        f"Busca iniciada em {resultado['datas'][0]}; "
        f"intervalo de {resultado['passo']} dia(s) entre datas. "
        "Menor preço entre os cartões reconhecidos nas datas com resultado; "
        "não representa todas as datas ou todas as ofertas disponíveis. "
        f"Verificação: {data_rss}."
    )
    if parcial:
        descricao += " Consulta parcial. Datas com falha: " + ", ".join(
            item["data"] for item in resultado["falhas"]
        ) + "."

    rss = ET.Element("rss", version="2.0")
    canal = ET.SubElement(rss, "channel")
    for tag, texto in (("title", f"Google Flights: {nome_rota}"),
                       ("link", resultado["url"]),
                       ("description", descricao), ("lastBuildDate", data_rss)):
        ET.SubElement(canal, tag).text = texto
    item = ET.SubElement(canal, "item")
    titulo = ("[Consulta parcial] " if parcial else "") + nome_rota + " → " + descrever_resultado(resultado)
    ET.SubElement(item, "title").text = titulo
    ET.SubElement(item, "link").text = resultado["url"]
    ET.SubElement(item, "pubDate").text = data_rss
    # Uma nova execução produz uma nova observação para o leitor RSS.
    identidade = resultado["url"] + nome_rota + agora.isoformat()
    ET.SubElement(item, "guid", isPermaLink="false").text = hashlib.sha256(
        identidade.encode("utf-8")).hexdigest()
    ET.SubElement(item, "description").text = formatar_artigo_html(titulo, descricao, resultado["url"], data_rss)
    ET.indent(rss, space="    ")
    conteudo = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    ET.fromstring(conteudo)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=pasta, suffix=".tmp", delete=False) as f:
            temporario = f.name
            f.write(conteudo)
        os.replace(temporario, caminho)
    finally:
        if temporario and os.path.exists(temporario):
            os.unlink(temporario)
    return str(caminho)


def resumo_final(atualizados, sem_preco, erros_gravacao, parciais):
    linhas = ["Varredura encerrada.",
              f"Feeds atualizados: {atualizados} (consultas parciais: {parciais}).",
              f"Rotas sem preço: {sem_preco}. Falhas ao gravar: {erros_gravacao}."]
    if atualizados:
        linhas.append(f"Feeds atualizados em: {PASTA_FEEDS}")
    else:
        linhas.append("Nenhum feed atualizado; feeds anteriores preservados.")
    return "\n".join(linhas)


def main():
    console.clear()
    mostrar_banner()
    ida_volta = escolher_tipo_viagem()
    duracao, duracao_nome = 7, None
    if ida_volta:
        duracao, duracao_nome = escolher_duracao()
    dias, passo, periodo_nome = escolher_periodo()
    destinos = escolher_destinos()
    atualizados = sem_preco = erros_gravacao = parciais = 0
    for nome, origem, destino in destinos:
        resultado = raspar_melhor_preco(
            nome, origem, destino, dias, passo, ida_volta, duracao)
        if resultado["preco"] is None:
            sem_preco += 1
            console.print("Feed anterior preservado; não contém uma nova consulta.",
                          style="yellow")
            continue
        try:
            caminho = criar_rss_local(nome, origem, destino, resultado,
                                      periodo_nome, ida_volta, duracao_nome)
        except OSError as erro:
            erros_gravacao += 1
            console.print(f"Falha ao gravar feed: {erro}", markup=False)
            continue
        atualizados += 1
        parciais += bool(resultado["falhas"])
        console.print(f"Feed atualizado: {caminho}", markup=False)
    cor = "yellow" if sem_preco or erros_gravacao or parciais else "green"
    from rich.text import Text
    console.print(Panel.fit(Text(resumo_final(
        atualizados, sem_preco, erros_gravacao, parciais)), border_style=cor))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\nConsulta interrompida pelo usuário.", style="yellow")
