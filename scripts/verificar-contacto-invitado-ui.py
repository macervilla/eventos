"""Numero de la agenda a Telefono/WhatsApp; API y contactos simulados, sin envios."""
import json
import os

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 396):
            context = browser.new_context(viewport=dict(width=ancho, height=900))
            context.add_init_script("""localStorage.setItem('eventos_sesion','prueba');
              window.contacto={name:['Ana Perez'],tel:['',' +54 9 2966 123456 '],email:[]};
              Object.defineProperty(navigator,'contacts',{value:{select:async()=>[window.contacto]}});""")
            guardados = []
            def api(route):
                ruta = route.request.url.split('?')[0]
                if route.request.method == 'POST' and ruta.endswith('/lista'):
                    guardados.append(route.request.post_data_json); datos = dict(id=1)
                elif ruta.endswith('/acceso/yo'):
                    datos = dict(email='owner@example.com', opciones=[])
                elif ruta.endswith('/acceso'):
                    datos = dict(permisos=['ver_invitados','editar_invitados'], usuario_id=1,
                        config=dict(activo=True,canales=['whatsapp']), roles_disponibles={})
                elif ruta.endswith('/lista'):
                    datos = dict(items=[],total=0)
                else: datos = {}
                route.fulfill(status=200, content_type='application/json', body=json.dumps(datos))
            context.route('**/api-vps/**', api)
            page = context.new_page()
            page.goto(os.getenv('EVENTOS_UI_URL','http://127.0.0.1:5180')+'/prueba/invitados')
            def abrir():
                page.get_by_role('button',name='Agregar invitado individual',exact=True).click()
                return page.get_by_role('dialog',name='Agregar invitado o grupo',exact=True)
            ventana = abrir()
            ventana.get_by_role('button',name='Elegir contacto del telefono',exact=True).click()
            expect(ventana.get_by_label('Telefono (opcional)',exact=True)).to_have_value('+54 9 2966 123456')
            expect(ventana.get_by_label('WhatsApp (numero con codigo de pais)',exact=True)).to_have_value('+54 9 2966 123456')
            ventana.get_by_role('button',name='Guardar',exact=True).click()
            expect(ventana).to_have_count(0)
            assert guardados[-1]['telefono'] == guardados[-1]['whatsapp'] == '+54 9 2966 123456'
            ventana = abrir()
            page.evaluate("window.contacto={name:['Luis'],tel:['02966 123456','+54 9 2966 654321'],email:[]}")
            ventana.get_by_role('button',name='Elegir contacto del telefono',exact=True).click()
            ventana.get_by_label('Numero del contacto',exact=False).select_option('+54 9 2966 654321')
            expect(ventana.get_by_label('Telefono (opcional)',exact=True)).to_have_value('+54 9 2966 654321')
            expect(ventana.get_by_label('WhatsApp (numero con codigo de pais)',exact=True)).to_have_value('+54 9 2966 654321')
            # Un WhatsApp indicado expresamente se conserva al elegir otro contacto.
            ventana.get_by_label('WhatsApp (numero con codigo de pais)',exact=True).fill('+54 9 2966 777777')
            page.evaluate("window.contacto={name:['Eva'],tel:['+54 9 2966 888888'],email:[]}")
            ventana.get_by_role('button',name='Elegir contacto del telefono',exact=True).click()
            expect(ventana.get_by_label('WhatsApp (numero con codigo de pais)',exact=True)).to_have_value('+54 9 2966 777777')
            expect(ventana.get_by_label('Telefono (opcional)',exact=True)).to_have_value('+54 9 2966 888888')
            # No se inventa ni borra un numero si el navegador no comparte el telefono.
            page.evaluate("window.contacto={name:['Sin telefono'],tel:[' '],email:[]}")
            ventana.get_by_role('button',name='Elegir contacto del telefono',exact=True).click()
            expect(ventana).to_contain_text('El contacto no compartio un numero de telefono')
            expect(ventana.get_by_label('Telefono (opcional)',exact=True)).to_have_value('+54 9 2966 888888')
            ventana.get_by_role('button',name='Guardar',exact=True).click()
            expect(ventana).to_have_count(0)
            assert guardados[-1]['whatsapp'] == '+54 9 2966 777777'
            assert guardados[-1]['telefono'] == '+54 9 2966 888888'
            context.close()
        browser.close()
    print('OK: numero automatico guardado en Telefono y WhatsApp, varios numeros, WhatsApp independiente y contacto sin telefono; movil y escritorio.')


if __name__ == '__main__':
    main()
