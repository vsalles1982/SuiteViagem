import json
import time
import unicodedata
from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from timezonefinder import TimezoneFinder


BASE_URL = "https://shotgun.live"
MAXIMO_PAGINAS = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

LOCALIZADOR_FUSO = TimezoneFinder()

DIAS_SEMANA = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

APELIDOS_CIDADES = {
    "lisboa": "lisbon",
    "londres": "london",
    "roma": "rome",
    "milao": "milan",
    "munique": "munich",
    "viena": "vienna",
    "nova york": "new-york",
    "nova iorque": "new-york",
    "cidade do mexico": "mexico-city",
}


def criar_slug(texto):
    texto_original = texto.strip().lower()

    if texto_original in APELIDOS_CIDADES:
        return APELIDOS_CIDADES[texto_original]

    texto_sem_acentos = unicodedata.normalize(
        "NFKD",
        texto_original,
    ).encode(
        "ascii",
        "ignore",
    ).decode("ascii")

    partes = texto_sem_acentos.split()
    return "-".join(partes)


def ler_data(mensagem):
    while True:
        valor = input(mensagem).strip()

        try:
            return datetime.strptime(
                valor,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            print(
                "Data inválida. Use o formato "
                "AAAA-MM-DD."
            )


def ler_quantidade():
    while True:
        valor = input(
            "Quantidade máxima de eventos (Ex: 10): "
        ).strip()

        try:
            quantidade = int(valor)

            if 1 <= quantidade <= 50:
                return quantidade

            print(
                "Digite uma quantidade entre 1 e 50."
            )

        except ValueError:
            print("Digite somente um número inteiro.")


def baixar_pagina(url):
    resposta = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    resposta.raise_for_status()

    return BeautifulSoup(
        resposta.text,
        "html.parser",
    )


def pagina_da_cidade_valida(pagina):
    titulo = pagina.find("h1")

    if not titulo:
        return False

    texto = titulo.get_text(
        " ",
        strip=True,
    ).lower()

    return "events in" in texto


def localizar_links_eventos(pagina):
    links = []
    vistos = set()

    for elemento in pagina.find_all(
        "a",
        href=True,
    ):
        endereco = elemento.get("href", "")

        if "/events/" not in endereco:
            continue

        endereco = urljoin(
            BASE_URL,
            endereco,
        )

        if endereco in vistos:
            continue

        vistos.add(endereco)
        links.append(endereco)

    return links


def localizar_music_event(pagina):
    blocos = pagina.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    )

    for bloco in blocos:
        conteudo = bloco.string or bloco.get_text()

        try:
            dados = json.loads(conteudo)
        except (json.JSONDecodeError, TypeError):
            continue

        if (
            isinstance(dados, dict)
            and dados.get("@type") == "MusicEvent"
        ):
            return dados

    return None


def converter_data(data_iso):
    return datetime.fromisoformat(
        data_iso.replace("Z", "+00:00")
    )


def obter_inicio_local(evento):
    inicio_iso = evento.get("startDate")

    if not inicio_iso:
        return None

    inicio = converter_data(inicio_iso)
    local = evento.get("location", {})

    if isinstance(local, dict):
        coordenadas = local.get("geo", {})
    else:
        coordenadas = {}

    if not isinstance(coordenadas, dict):
        coordenadas = {}

    latitude = coordenadas.get("latitude")
    longitude = coordenadas.get("longitude")

    if (
        latitude is not None
        and longitude is not None
    ):
        nome_fuso = LOCALIZADOR_FUSO.timezone_at(
            lat=float(latitude),
            lng=float(longitude),
        )

        if nome_fuso:
            inicio = inicio.astimezone(
                ZoneInfo(nome_fuso)
            )

    return inicio


def obter_periodo_local(evento):
    inicio = obter_inicio_local(evento)
    final_iso = evento.get("endDate")

    if not inicio:
        return (
            "Não informada",
            "Não informado",
        )

    final = None

    if final_iso:
        final = converter_data(final_iso)

        local = evento.get("location", {})

        if isinstance(local, dict):
            coordenadas = local.get("geo", {})
        else:
            coordenadas = {}

        if isinstance(coordenadas, dict):
            latitude = coordenadas.get("latitude")
            longitude = coordenadas.get("longitude")

            if (
                latitude is not None
                and longitude is not None
            ):
                nome_fuso = (
                    LOCALIZADOR_FUSO.timezone_at(
                        lat=float(latitude),
                        lng=float(longitude),
                    )
                )

                if nome_fuso:
                    final = final.astimezone(
                        ZoneInfo(nome_fuso)
                    )

    dia_semana = DIAS_SEMANA[inicio.weekday()]

    data_formatada = (
        f"{dia_semana}, "
        f"{inicio.strftime('%d/%m/%Y')}"
    )

    if not final:
        horario = inicio.strftime("%H:%M")

    elif inicio.date() == final.date():
        horario = (
            f"{inicio.strftime('%H:%M')} até "
            f"{final.strftime('%H:%M')}"
        )

    else:
        horario = (
            f"{inicio.strftime('%H:%M')} até "
            f"{final.strftime('%H:%M')} "
            f"({final.strftime('%d/%m/%Y')})"
        )

    return data_formatada, horario


def obter_preco(evento):
    ofertas = evento.get("offers", [])

    if isinstance(ofertas, dict):
        ofertas = [ofertas]

    precos = []

    for oferta in ofertas:
        preco = oferta.get("price")
        moeda = oferta.get("priceCurrency", "")

        if isinstance(preco, (int, float)):
            precos.append(
                (float(preco), moeda)
            )

    if not precos:
        return "Não informado"

    menor_preco, moeda = min(
        precos,
        key=lambda item: item[0],
    )

    simbolos = {
        "EUR": "€",
        "BRL": "R$",
        "USD": "US$",
        "GBP": "£",
    }

    simbolo = simbolos.get(moeda, moeda)

    if menor_preco.is_integer():
        valor = str(int(menor_preco))
    else:
        valor = f"{menor_preco:.2f}"

    return f"{simbolo} {valor}".strip()


def obter_local(evento):
    local = evento.get("location", {})

    if not isinstance(local, dict):
        return "Não informado"

    endereco = local.get("address", {})

    if isinstance(endereco, dict):
        rua = endereco.get("streetAddress", "")
        cidade = endereco.get(
            "addressLocality",
            "",
        )

        if rua:
            return rua

        if cidade:
            return cidade

    return local.get(
        "name",
        "Não informado",
    )


def obter_organizador(evento):
    organizador = evento.get("organizer", {})

    if isinstance(organizador, dict):
        return organizador.get(
            "name",
            "Não informado",
        )

    return "Não informado"


def resumir_lineup(evento):
    artistas = evento.get("performer", [])

    if isinstance(artistas, dict):
        artistas = [artistas]

    nomes = []

    for artista in artistas:
        if (
            isinstance(artista, dict)
            and artista.get("name")
        ):
            nomes.append(artista["name"])

    if nomes:
        return ", ".join(nomes)

    descricao = evento.get(
        "description",
        "",
    ).strip()

    if not descricao:
        return "Não informado"

    linhas = [
        linha.strip(" •-\t")
        for linha in descricao.splitlines()
        if linha.strip()
    ]

    for indice, linha in enumerate(linhas):
        linha_maiuscula = linha.upper()

        if (
            "LINE UP" in linha_maiuscula
            or "LINE-UP" in linha_maiuscula
        ):
            candidatos = []

            for proxima in linhas[
                indice + 1:indice + 7
            ]:
                texto_maiusculo = proxima.upper()

                if (
                    "IMPORTANT" in texto_maiusculo
                    or "IMPORTANTE" in texto_maiusculo
                    or ":" in proxima
                ):
                    break

                candidatos.append(proxima)

            if candidatos:
                return ", ".join(candidatos)

    return "Consulte a página do evento"


def mostrar_evento(numero, evento):
    data, horario = obter_periodo_local(evento)

    print(
        f"{numero}. "
        f"{evento.get('name', 'Evento sem nome')}"
    )
    print(f"   Data:         {data}")
    print(f"   Horário:      {horario}")
    print(f"   Local:        {obter_local(evento)}")
    print(
        f"   Organização:  "
        f"{obter_organizador(evento)}"
    )
    print(
        f"   Line-up:      "
        f"{resumir_lineup(evento)}"
    )

    preco = obter_preco(evento)

    if preco == "Não informado":
        print("   Ingresso:     Não informado")
    else:
        print(
            f"   Ingresso:     "
            f"a partir de {preco}"
        )

    print(
        f"   Link:         "
        f"{evento.get('url', 'Não informado')}"
    )
    print()


def coletar_links(url_cidade):
    todos_links = []
    links_vistos = set()

    for pagina_numero in range(
        1,
        MAXIMO_PAGINAS + 1,
    ):
        if pagina_numero == 1:
            url = url_cidade
        else:
            url = (
                f"{url_cidade}"
                f"?page={pagina_numero}"
            )

        print(
            f"\rLendo página "
            f"{pagina_numero} da agenda...",
            end="",
            flush=True,
        )

        pagina = baixar_pagina(url)
        links = localizar_links_eventos(pagina)

        novos = 0

        for link in links:
            if link not in links_vistos:
                links_vistos.add(link)
                todos_links.append(link)
                novos += 1

        if novos == 0:
            break

        time.sleep(0.5)

    print(
        "\r" + " " * 60 + "\r",
        end="",
    )

    return todos_links


def buscar_eventos(
    links,
    data_inicial,
    data_final,
    quantidade,
):
    encontrados = []

    for numero, link in enumerate(
        links,
        start=1,
    ):
        print(
            f"\rAnalisando evento "
            f"{numero}/{len(links)}...",
            end="",
            flush=True,
        )

        pagina = baixar_pagina(link)
        evento = localizar_music_event(pagina)

        if not evento:
            continue

        inicio_local = obter_inicio_local(evento)

        if not inicio_local:
            continue

        data_evento = inicio_local.date()

        if data_inicial <= data_evento <= data_final:
            encontrados.append(evento)

            if len(encontrados) >= quantidade:
                break

        time.sleep(0.6)

    print(
        "\r" + " " * 60 + "\r",
        end="",
    )

    return encontrados


def main():
    print("=" * 55)
    print(" SHOTGUN — BUSCADOR DE EVENTOS")
    print(" Música eletrônica e cena underground")
    print("=" * 55)
    print()

    cidade = input(
        "Destino (Ex: Ibiza, São Paulo, Lisboa): "
    ).strip()

    if not cidade:
        print("O destino não pode ficar vazio.")
        return

    data_inicial = ler_data(
        "Data inicial (AAAA-MM-DD): "
    )

    data_final = ler_data(
        "Data final   (AAAA-MM-DD): "
    )

    if data_final < data_inicial:
        print(
            "A data final não pode ser anterior "
            "à data inicial."
        )
        return

    quantidade = ler_quantidade()
    slug = criar_slug(cidade)

    url_cidade = (
        f"{BASE_URL}/en/cities/{slug}"
    )

    print()
    print(f"Consultando: {url_cidade}")
    print()

    try:
        primeira_pagina = baixar_pagina(
            url_cidade
        )

        if not pagina_da_cidade_valida(
            primeira_pagina
        ):
            print(
                "A cidade não foi encontrada "
                "no Shotgun."
            )
            print(
                "Confira o nome e tente novamente."
            )
            return

        links = coletar_links(url_cidade)

        if not links:
            print(
                "Nenhum evento foi encontrado "
                "na agenda dessa cidade."
            )
            return

        print(
            f"{len(links)} eventos localizados "
            f"na agenda."
        )
        print()

        eventos = buscar_eventos(
            links,
            data_inicial,
            data_final,
            quantidade,
        )

        if not eventos:
            print(
                "Nenhum evento foi encontrado "
                "dentro desse período."
            )
            return

        print(
            f"Encontrados {len(eventos)} eventos "
            f"em {cidade}:"
        )
        print()

        for numero, evento in enumerate(
            eventos,
            start=1,
        ):
            mostrar_evento(numero, evento)

        print(
            "Agenda complementar no "
            "Resident Advisor:"
        )
        print(
            f"https://ra.co/events/"
        )

    except requests.RequestException as erro:
        print()
        print(f"Erro de conexão: {erro}")

    except KeyboardInterrupt:
        print()
        print(
            "Busca interrompida pelo usuário."
        )

    except Exception as erro:
        print()
        print(f"Erro inesperado: {erro}")


if __name__ == "__main__":
    main()
