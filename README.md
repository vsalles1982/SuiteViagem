# Suíte de Viagem

Ferramentas em Python para pesquisar passagens, hospedagens, aluguel de carros e eventos durante uma viagem.

A suíte reúne quatro módulos independentes, com interfaces gráficas e de terminal. O planejamento futuro inclui feeds RSS centralizados no Newsboat e atualizações automáticas.

## Módulos

### ✈️ Google Flights

Pesquisa rotas e preços utilizando Playwright.

```bash
python passagens/google-flights/gerar_feeds_voos.py
```

Recursos:

- rotas personalizadas e predefinidas;
- seleção de períodos;
- interface com Rich;
- geração de resultados para acompanhamento;
- base para o futuro feed RSS de passagens.

### 🏨 Booking

Pesquisa hotéis por destino e período utilizando Selenium.

```bash
python booking-hotel-scraper/hotels_booking.py
```

Recursos:

- interface gráfica com Tkinter;
- pesquisa por cidade e datas;
- distância até pontos de referência;
- organização dos resultados com Pandas;
- exportação local para Excel.

### 🚗 DiscoverCars

Pesquisa veículos e preços utilizando Selenium.

```bash
python scraper_carro/discovercars.py
```

Recursos:

- interface Textual;
- busca por destino e período;
- listagem de veículos, locadoras e preços;
- exportação local dos resultados;
- tratamento de páginas dinâmicas.

### 🎧 Shotgun

Pesquisa eventos de música eletrônica e da cena underground no período da viagem.

Terminal:

```bash
python shotgun-events-scraper/shotgun.py
```

Interface Textual:

```bash
python shotgun-events-scraper/shotgun_tui.py
```

Recursos:

- busca por cidade e intervalo de datas;
- conversão para o fuso horário local;
- local, organização, line-up e ingresso;
- interface Textual;
- busca em segundo plano.

## Estrutura

```text
suite-viagem/
├── passagens/
│   └── google-flights/
│       ├── gerar_feeds_voos.py
│       └── legacy/
├── booking-hotel-scraper/
│   ├── hotels_booking.py
│   ├── legacy/
│   └── requirements.txt
├── scraper_carro/
│   ├── discovercars.py
│   └── legacy/
├── shotgun-events-scraper/
│   ├── shotgun.py
│   ├── shotgun_terminal_estavel.py
│   └── shotgun_tui.py
├── .gitignore
├── README.md
└── requirements.txt
```

## Instalação

Requer Python 3.11 ou superior.

No Arch Linux, instale o suporte ao Tkinter:

```bash
sudo pacman -S tk
```

Crie e ative um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

Instale o navegador do Playwright:

```bash
playwright install chromium
```

## Planejamento futuro

- padronizar a saída dos módulos;
- gerar feeds RSS separados;
- reunir os feeds no Newsboat;
- automatizar consultas com timers do systemd;
- registrar históricos de preços;
- destacar quedas de preços e novos eventos;
- criar uma interface inicial para toda a suíte.

## Radar de viagem

```text
Google Flights ─┐
Booking ─────────┤
DiscoverCars ────┼──> Feeds RSS ──> Newsboat
Shotgun ─────────┘
```

## Aviso

Os sites consultados podem alterar suas páginas, seletores e regras de acesso. Utilize as ferramentas de forma responsável, respeitando termos de uso, limites de acesso e a legislação aplicável.

Este projeto não possui vínculo oficial com Google Flights, Booking, DiscoverCars ou Shotgun.
