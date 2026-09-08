import io
from contextlib import redirect_stdout
from datetime import datetime

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
)

import shotgun_terminal_estavel as motor


class ShotgunApp(App):
    TITLE = "Shotgun Events Scraper"
    SUB_TITLE = "Música eletrônica e cena underground"

    CSS = """
    Screen {
        background: #101018;
        color: #f2f2f2;
    }

    Header {
        background: #181824;
        color: #ff4f70;
    }

    #painel {
        width: 92%;
        max-width: 105;
        height: auto;
        margin: 1 4;
        padding: 1 2;
        border: round #ff4f70;
        background: #181824;
    }

    #titulo {
        width: 100%;
        content-align: center middle;
        color: #ff4f70;
        text-style: bold;
        margin-bottom: 1;
    }

    Label {
        margin-top: 1;
        color: #d8d8e8;
    }

    Input {
        margin-top: 0;
        border: tall #55556f;
        background: #20202d;
    }

    Input:focus {
        border: tall #ff4f70;
    }

    #buscar {
        width: 100%;
        margin-top: 2;
        background: #ff4f70;
        color: #ffffff;
        text-style: bold;
    }

    #buscar:hover {
        background: #ff708b;
    }

    #buscar:disabled {
        background: #55556f;
        color: #aaaaaa;
    }

    #status {
        width: 100%;
        margin-top: 1;
        color: #ffd166;
    }

    #resultados {
        width: 100%;
        height: 28;
        margin-top: 1;
        padding: 1;
        border: round #55556f;
        background: #11111a;
        color: #f2f2f2;
    }

    Footer {
        background: #181824;
    }
    """

    BINDINGS = [
        ("q", "quit", "Sair"),
        ("ctrl+r", "limpar", "Limpar"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="painel"):
            yield Static(
                "🎧 SHOTGUN — BUSCADOR DE EVENTOS",
                id="titulo",
            )

            yield Label("Destino")
            yield Input(
                placeholder="Ex: Ibiza, São Paulo, Lisboa",
                id="cidade",
            )

            yield Label("Data inicial — AAAA-MM-DD")
            yield Input(
                placeholder="Ex: 2026-08-14",
                id="data_inicial",
            )

            yield Label("Data final — AAAA-MM-DD")
            yield Input(
                placeholder="Ex: 2026-08-18",
                id="data_final",
            )

            yield Label("Quantidade máxima")
            yield Input(
                value="10",
                placeholder="Ex: 10",
                id="quantidade",
            )

            yield Button(
                "BUSCAR EVENTOS",
                id="buscar",
                variant="primary",
            )

            yield Static(
                "Preencha os campos para iniciar.",
                id="status",
            )

            yield RichLog(
                id="resultados",
                wrap=True,
                markup=False,
                auto_scroll=True,
            )

        yield Footer()

    def action_limpar(self) -> None:
        resultados = self.query_one(
            "#resultados",
            RichLog,
        )

        resultados.clear()

        self.query_one(
            "#status",
            Static,
        ).update(
            "Resultados apagados."
        )

    def validar_campos(self):
        cidade = self.query_one(
            "#cidade",
            Input,
        ).value.strip()

        texto_inicial = self.query_one(
            "#data_inicial",
            Input,
        ).value.strip()

        texto_final = self.query_one(
            "#data_final",
            Input,
        ).value.strip()

        texto_quantidade = self.query_one(
            "#quantidade",
            Input,
        ).value.strip()

        if not cidade:
            raise ValueError(
                "Informe uma cidade."
            )

        try:
            data_inicial = datetime.strptime(
                texto_inicial,
                "%Y-%m-%d",
            ).date()

            data_final = datetime.strptime(
                texto_final,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            raise ValueError(
                "Use datas no formato AAAA-MM-DD."
            )

        if data_final < data_inicial:
            raise ValueError(
                "A data final não pode ser anterior "
                "à data inicial."
            )

        try:
            quantidade = int(texto_quantidade)
        except ValueError:
            raise ValueError(
                "A quantidade deve ser um número."
            )

        if quantidade < 1 or quantidade > 50:
            raise ValueError(
                "Digite uma quantidade entre 1 e 50."
            )

        return (
            cidade,
            data_inicial,
            data_final,
            quantidade,
        )

    def on_button_pressed(
        self,
        evento: Button.Pressed,
    ) -> None:
        if evento.button.id != "buscar":
            return

        status = self.query_one(
            "#status",
            Static,
        )

        try:
            dados = self.validar_campos()

        except ValueError as erro:
            status.update(str(erro))
            return

        cidade, data_inicial, data_final, quantidade = dados

        resultados = self.query_one(
            "#resultados",
            RichLog,
        )

        resultados.clear()

        evento.button.disabled = True
        evento.button.label = "BUSCANDO..."

        status.update(
            f"Consultando eventos em {cidade}..."
        )

        self.executar_busca(
            cidade,
            data_inicial,
            data_final,
            quantidade,
        )

    @work(
        thread=True,
        exclusive=True,
    )
    def executar_busca(
        self,
        cidade,
        data_inicial,
        data_final,
        quantidade,
    ) -> None:
        try:
            slug = motor.criar_slug(cidade)

            url_cidade = (
                f"{motor.BASE_URL}/en/cities/{slug}"
            )

            pagina = motor.baixar_pagina(
                url_cidade
            )

            if not motor.pagina_da_cidade_valida(
                pagina
            ):
                self.call_from_thread(
                    self.mostrar_erro,
                    "Cidade não encontrada no Shotgun. "
                    "Confira o nome informado.",
                )
                return

            saida_oculta = io.StringIO()
            resumo = {}

            with redirect_stdout(saida_oculta):
                links = motor.coletar_links(
                    url_cidade, resumo=resumo
                )

            self.call_from_thread(
                self.atualizar_status,
                f"{len(links)} links localizados. "
                f"Filtrando o período...",
            )

            with redirect_stdout(saida_oculta):
                eventos = motor.buscar_eventos(
                    links,
                    data_inicial,
                    data_final,
                    quantidade,
                    resumo=resumo,
                )

            eventos.sort(
                key=lambda item: (
                    motor.obter_inicio_local(item)
                    or datetime.max.astimezone()
                )
            )

            try:
                arquivos = motor.exportar_resultados(
                    cidade, data_inicial, data_final, eventos, resumo
                )
                exportacao = "Arquivos salvos:\n" + "\n".join(arquivos)
            except Exception as erro:
                exportacao = f"FALHA AO EXPORTAR: {erro}. Os resultados continuam abaixo."

            self.call_from_thread(
                self.mostrar_resultados,
                cidade,
                eventos,
                resumo,
                exportacao,
            )

        except Exception as erro:
            self.call_from_thread(
                self.mostrar_erro,
                f"Erro durante a busca: {erro}",
            )

    def atualizar_status(
        self,
        mensagem,
    ) -> None:
        self.query_one(
            "#status",
            Static,
        ).update(mensagem)

    def restaurar_botao(self) -> None:
        botao = self.query_one(
            "#buscar",
            Button,
        )

        botao.disabled = False
        botao.label = "BUSCAR EVENTOS"

    def mostrar_erro(
        self,
        mensagem,
    ) -> None:
        self.query_one(
            "#status",
            Static,
        ).update(mensagem)

        resultados = self.query_one(
            "#resultados",
            RichLog,
        )

        resultados.write(
            f"ERRO\n\n{mensagem}"
        )

        self.restaurar_botao()

    def mostrar_sem_resultados(
        self,
        cidade,
        data_inicial,
        data_final,
    ) -> None:
        mensagem = (
            f"Nenhum evento foi encontrado em "
            f"{cidade} entre "
            f"{data_inicial.strftime('%d/%m/%Y')} e "
            f"{data_final.strftime('%d/%m/%Y')}."
        )

        self.query_one(
            "#status",
            Static,
        ).update(
            "Busca concluída sem resultados."
        )

        resultados = self.query_one(
            "#resultados",
            RichLog,
        )

        resultados.write(mensagem)
        resultados.write("")
        resultados.write(
            "Agenda complementar:"
        )
        resultados.write(
            "https://ra.co/events"
        )

        self.restaurar_botao()

    def mostrar_resultados(
        self,
        cidade,
        eventos,
        resumo,
        exportacao,
    ) -> None:
        resultados = self.query_one(
            "#resultados",
            RichLog,
        )

        resultados.clear()

        resultados.write(
            "SHOTGUN — EVENTOS ENCONTRADOS"
        )
        resultados.write(
            "=" * 55
        )
        resultados.write(
            f"Destino: {cidade}"
        )
        resultados.write(motor.descrever_cobertura(resumo))
        resultados.write(exportacao)
        resultados.write("")
        if not eventos:
            resultados.write("Nenhum evento retornado nos links analisados. Confira a cobertura acima.")

        for numero, evento in enumerate(
            eventos,
            start=1,
        ):
            data, horario = (
                motor.obter_periodo_local(evento)
            )

            nome = evento.get(
                "name",
                "Evento sem nome",
            )

            local = motor.obter_local(evento)
            organizador = (
                motor.obter_organizador(evento)
            )
            lineup = motor.resumir_lineup(evento)
            preco = motor.obter_preco(evento)
            link = evento.get(
                "url",
                "Não informado",
            )

            resultados.write(
                f"{numero}. {nome}"
            )
            resultados.write(
                f"   Data:        {data}"
            )
            resultados.write(
                f"   Horário:     {horario}"
            )
            resultados.write(
                f"   Local:       {local}"
            )
            resultados.write(
                f"   Organização: {organizador}"
            )
            resultados.write(
                f"   Line-up:     {lineup}"
            )

            if preco == "Não informado":
                resultados.write(
                    "   Ingresso:    Não informado"
                )
            else:
                resultados.write(
                    f"   Ingresso:    "
                    f"a partir de {preco}"
                )

            resultados.write(
                f"   Link:        {link}"
            )
            resultados.write("")

        resultados.write(
            "=" * 55
        )
        resultados.write(
            "Agenda complementar:"
        )
        resultados.write(
            "https://ra.co/events"
        )

        self.query_one(
            "#status",
            Static,
        ).update(
            f"Busca encerrada: {len(eventos)} eventos retornados. Confira cobertura e exportação."
        )

        self.restaurar_botao()


if __name__ == "__main__":
    ShotgunApp().run()
