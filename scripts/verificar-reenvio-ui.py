"""Prueba del envio simplificado con API simulada; no envia mensajes externos."""
import json
import os
import tempfile
from pathlib import Path
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright, expect


def comprobar_lote(browser, imagen, ancho, admite_fotos):
    page = browser.new_page(viewport={'width': ancho, 'height': 900}, accept_downloads=True)
    page.add_init_script("""localStorage.setItem('eventos_sesion','prueba');
      window.enviosFoto=[];window.chats=[];
      window.open=url=>{window.chats.push(url);return null;};
      window.compartirSimulado=async datos=>{window.enviosFoto.push(datos.text);};
      navigator.share=window.compartirSimulado;
      navigator.canShare=()=>%s;""" % str(admite_fotos).lower())
    personas = [dict(id=n, nombre=nombre, apellido='', canal='whatsapp', distribucion='PREPARADO',
                     whatsapp=f'+549111234567{n}', activo=True, nombres_menores=[]) for n, nombre in ((1, 'Ana'), (2, 'Luis'))]
    peticiones = []

    def api(route):
        url = route.request.url.split('?')[0]
        data = {}
        if url.endswith('/acceso/yo'):
            data = dict(email='prueba@example.com', opciones=[])
        elif url.endswith('/acceso'):
            data = dict(permisos=['ver_invitados', 'distribuir'], config=dict(activo=True, canales=['whatsapp']), roles_disponibles={})
        elif url.endswith('/lista'):
            data = dict(total=2, items=personas)
        elif url.endswith('/portada.jpg'):
            route.fulfill(status=200, content_type='image/jpeg', body=imagen.getvalue())
            return
        elif url.endswith('/distribuir'):
            peticiones.append(route.request.post_data_json)
            data = dict(resultados=[dict(id=i['id'], destinatario=i['nombre'], estado='PREPARADO', canal='whatsapp',
                mensaje=f"Hola {i['nombre']}", enlace=f"https://example.com/invitacion-{i['id']}",
                url_canal=f"https://wa.me/{i['id']}?text=invitacion-{i['id']}") for i in personas])
        route.fulfill(status=200, content_type='application/json', body=json.dumps(data))

    page.route('**/api-vps/**', api)
    page.goto(os.getenv('EVENTOS_UI_URL', 'http://localhost:5179') + '/prueba/invitados')
    for nombre in ('Ana', 'Luis'):
        page.get_by_role('checkbox', name=f'Seleccionar {nombre}', exact=True).check()
    page.get_by_role('button', name='Enviar / Reenviar seleccion (2)', exact=True).click()
    popup = page.get_by_role('dialog', name='Enviar invitacion', exact=True)
    expect(popup).to_be_visible()
    selector = popup.get_by_label('Destinatario para reenviar', exact=True)
    expect(selector).to_have_value('0')
    expect(popup.locator('button:visible')).to_have_count(2)
    assert len(peticiones) == 1 and peticiones[0]['ids'] == [1, 2]
    if admite_fotos:
        boton = popup.get_by_role('button', name='Compartir foto y mensaje', exact=True)
        expect(boton).to_have_count(1)
        # Cancelar no consume la invitacion ni avanza al siguiente destinatario.
        page.evaluate("() => { navigator.share=async()=>{throw new DOMException('Cancelado','AbortError');}; }")
        boton.click()
        expect(popup.get_by_text('Compartir cancelado. Podes volver a intentarlo.')).to_be_visible()
        expect(selector).to_have_value('0')
        assert page.evaluate('window.enviosFoto.length') == 0
        page.evaluate('() => { navigator.share=window.compartirSimulado; }')
        boton.click()
        expect(selector).to_have_value('1')
        expect(popup.locator('article > strong')).to_have_text('Luis')
        boton.click()
        mensajes = page.evaluate('window.enviosFoto')
        assert len(mensajes) == 2
        assert 'Hola Ana' in mensajes[0] and 'invitacion-1' in mensajes[0] and 'invitacion-2' not in mensajes[0]
        assert 'Hola Luis' in mensajes[1] and 'invitacion-2' in mensajes[1] and 'invitacion-1' not in mensajes[1]
    else:
        boton = popup.get_by_role('button', name='Descargar foto y abrir chat', exact=True)
        expect(boton).to_have_count(1)
        for indice in range(2):
            with page.expect_download() as descarga:
                boton.click()
            assert descarga.value.suggested_filename == 'invitacion.jpg'
            expect(selector).to_have_value('1')
        assert page.evaluate('window.chats') == [f'https://wa.me/{n}?text=invitacion-{n}' for n in (1, 2)]
    # El selector permite repetir una invitacion anterior usando el mismo boton.
    selector.select_option('0')
    expect(popup.locator('article > strong')).to_have_text('Ana')
    expect(popup.locator('button:visible')).to_have_count(2)
    assert popup.evaluate('e => e.scrollWidth <= e.clientWidth')
    if admite_fotos:
        page.screenshot(path=str(Path(tempfile.gettempdir()) / f'eventos-envio-lote-{ancho}.png'))
    page.keyboard.press('Escape')
    expect(popup).to_have_count(0)
    page.close()


def comprobar_canales(browser, ancho):
    page = browser.new_page(viewport={'width': ancho, 'height': 900})
    page.add_init_script("localStorage.setItem('eventos_sesion','prueba')")
    personas = [
        dict(id=1, nombre='Solo correo', email='invitado@gmail.com', canal='whatsapp', distribucion='FALLIDO'),
        dict(id=2, nombre='Correo nuevo', email='nuevo@gmail.com', canal=None, distribucion='PENDIENTE'),
        dict(id=3, nombre='Instagram', instagram='@invitado', canal='whatsapp', distribucion='FALLIDO'),
        dict(id=4, nombre='WhatsApp', whatsapp='+5491112345678', email='otro@gmail.com', canal='whatsapp', distribucion='PREPARADO'),
    ]
    for persona in personas:
        persona.update(apellido='', activo=True, nombres_menores=[])
    peticiones = []

    def api(route):
        url = route.request.url.split('?')[0]
        data = {}
        if url.endswith('/acceso/yo'):
            data = dict(email='prueba@example.com', opciones=[])
        elif url.endswith('/acceso'):
            data = dict(permisos=['ver_invitados', 'distribuir'], config=dict(activo=True, canales=['whatsapp', 'email', 'instagram']), roles_disponibles={})
        elif url.endswith('/lista'):
            data = dict(total=len(personas), items=personas)
        elif url.endswith('/distribuir'):
            envio = route.request.post_data_json
            peticiones.append(envio)
            data = dict(resultados=[dict(id=i, canal=envio['canal'], estado='ENVIADO' if envio['canal'] == 'email' else 'PREPARADO') for i in envio['ids']])
        route.fulfill(status=200, content_type='application/json', body=json.dumps(data))

    page.route('**/api-vps/**', api)
    page.goto(os.getenv('EVENTOS_UI_URL', 'http://localhost:5179') + '/prueba/invitados')
    fila = page.get_by_role('row').filter(has=page.get_by_text('Solo correo', exact=True))
    fila.get_by_role('button', name='Enviar invitacion', exact=True).click()
    confirmacion = page.get_by_role('dialog', name='Reenviar invitacion', exact=True)
    expect(confirmacion).to_contain_text('Solo correo : email')
    confirmacion.get_by_role('button', name='Cancelar', exact=True).click()
    assert peticiones == []
    fila.get_by_role('button', name='Enviar invitacion', exact=True).click()
    confirmacion.get_by_role('button', name='Confirmar envio', exact=True).click()
    expect(page.get_by_text('Invitacion enviada al servidor de correo.', exact=True)).to_be_visible()
    assert [(p['ids'], p['canal']) for p in peticiones] == [([1], 'email')]
    for persona in personas:
        page.get_by_role('checkbox', name=f"Seleccionar {persona['nombre']}", exact=True).check()
    page.get_by_role('button', name='Enviar / Reenviar seleccion (4)', exact=True).click()
    expect(confirmacion).to_contain_text('Correo nuevo : email')
    expect(confirmacion).to_contain_text('Instagram : instagram')
    expect(confirmacion).to_contain_text('WhatsApp : whatsapp')
    confirmacion.get_by_role('button', name='Preparar invitaciones', exact=True).click()
    expect(page.get_by_role('dialog', name='Enviar invitacion', exact=True)).to_be_visible()
    assert [(p['ids'], p['canal']) for p in peticiones[1:]] == [([1, 2], 'email'), ([3], 'instagram'), ([4], 'whatsapp')]
    page.close()


def main():
    imagen = BytesIO()
    Image.new('RGB', (80, 120), 'green').save(imagen, format='JPEG')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 396):
            comprobar_canales(browser, ancho)
            for admite_fotos in (False, True):
                page = browser.new_page(viewport={'width': ancho, 'height': 900}, accept_downloads=True)
                page.add_init_script("""localStorage.setItem('eventos_sesion','prueba');
                  window.enviosFoto=[]; window.chats=[];
                  window.open=(url)=>{window.chats.push(url);return null;};
                  navigator.share=async datos=>{window.enviosFoto.push({nombre:datos.files[0].name,bytes:datos.files[0].size,texto:datos.text});};
                  Object.defineProperty(navigator,'clipboard',{value:{writeText:async texto=>window.textoCopiado=texto}});
                  navigator.canShare=()=>%s;""" % str(admite_fotos).lower())
                def api(route):
                    url = route.request.url.split('?')[0]
                    data = {}
                    if url.endswith('/acceso/yo'): data=dict(email='prueba@example.com',opciones=[])
                    elif url.endswith('/acceso'): data=dict(permisos=['ver_invitados','distribuir','configurar_evento'],config=dict(activo=True,canales=['whatsapp','email']),roles_disponibles={})
                    elif url.endswith('/lista'): data=dict(total=1,items=[dict(id=1,nombre='Ana',apellido='',whatsapp='+5491112345678',canal='whatsapp',distribucion='PREPARADO',activo=True,nombres_menores=[])])
                    elif url.endswith('/portada.jpg'):
                        route.fulfill(status=200,content_type='image/jpeg',body=imagen.getvalue()); return
                    elif url.endswith('/distribuir'): data=dict(resultados=[dict(id=1,destinatario='Ana',telefono_destino='+5491112345678',estado='PREPARADO',canal='whatsapp',mensaje='Hola Ana',enlace='https://example.com/invitacion',url_canal='https://wa.me/5491112345678?text=Prueba')])
                    route.fulfill(status=200,content_type='application/json',body=json.dumps(data))
                page.route('**/api-vps/**',api)
                page.on('dialog',lambda d: (_ for _ in ()).throw(AssertionError('Dialogo nativo inesperado')))
                page.goto(os.getenv('EVENTOS_UI_URL', 'http://localhost:5179') + '/prueba/invitados')
                page.get_by_role('button',name='Reenviar invitacion',exact=True).click()
                popup=page.get_by_role('dialog',name='Enviar invitacion',exact=True)
                expect(popup).to_be_visible()
                portada = popup.get_by_role('img', name='Portada de la invitación')
                enlace = popup.get_by_role('link', name='Confirmar asistencia')
                expect(portada).to_be_visible()
                expect(enlace).to_have_attribute('href', 'https://example.com/invitacion')
                assert portada.bounding_box()['y'] + portada.bounding_box()['height'] <= enlace.bounding_box()['y']
                expect(popup.get_by_role('button',name='Copiar foto y abrir WhatsApp')).to_have_count(0)
                expect(popup.get_by_role('button',name='Copiar texto y enlace')).not_to_be_visible()
                # Un unico boton principal, mas la cruz para cerrar.
                expect(popup.locator('button:visible')).to_have_count(2)
                if admite_fotos and ancho == 396:
                    page.screenshot(path=str(Path(tempfile.gettempdir()) / 'eventos-envio-simple.png'))
                if admite_fotos:
                    popup.get_by_role('button',name='Compartir foto y mensaje',exact=True).click()
                    expect(popup.get_by_text('Compartido con la aplicacion elegida;',exact=False)).to_be_visible()
                    foto=page.evaluate('window.enviosFoto[0]')
                    assert foto['nombre']=='invitacion.jpg' and foto['bytes']>0
                    assert foto['texto'].splitlines()[-1] == 'https://example.com/invitacion'
                    page.evaluate("() => {navigator.share=async()=>{throw new DOMException('Cancelado','AbortError');};}")
                    popup.get_by_role('button',name='Compartir foto y mensaje',exact=True).click()
                    expect(popup.get_by_text('Compartir cancelado. Podes volver a intentarlo.')).to_be_visible()
                else:
                    popup.get_by_text('Más opciones', exact=True).click()
                    popup.get_by_role('button', name='Copiar texto y enlace').click()
                    assert page.evaluate('window.textoCopiado').splitlines()[-1] == 'https://example.com/invitacion'
                    popup.get_by_text('Más opciones', exact=True).click()
                    with page.expect_download() as descarga:
                        popup.get_by_role('button',name='Descargar foto y abrir chat',exact=True).click()
                    assert descarga.value.suggested_filename=='invitacion.jpg'
                    assert page.evaluate('window.chats[0]').startswith('https://wa.me/')
                page.keyboard.press('Escape')
                expect(popup).to_have_count(0)
                page.close()
                comprobar_lote(browser, imagen, ancho, admite_fotos)
        browser.close()
    print('OK: una ventana, una accion principal, foto y enlace, descarga alternativa y cancelacion; escritorio y movil.')

if __name__=='__main__':
    main()
