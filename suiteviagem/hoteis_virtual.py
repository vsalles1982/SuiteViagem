"""Entrada dos hotéis dentro do display X11 privado iniciado pelo servidor."""
import os
import runpy

def main():
    if not os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        raise SystemExit('Display virtual não configurado; execute pelo servidor da Suíte.')
    from selenium import webdriver
    original = webdriver.ChromeOptions
    def options():
        result = original()
        result.add_argument('--ozone-platform=x11')
        return result
    webdriver.ChromeOptions = options
    print('Booking em display virtual: a janela fica fora da sua tela.', flush=True)
    try:
        runpy.run_module('suiteviagem.hoteis', run_name='__main__')
    finally:
        webdriver.ChromeOptions = original

if __name__ == '__main__':
    main()
