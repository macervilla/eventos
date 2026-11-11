"""Prueba del envio simplificado con API simulada; no envia mensajes externos."""
import json
import tempfile
from pathlib import Path
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright, expect


def main():
    imagen = BytesIO()
    Image.new('RGB', (80, 120), 'green').save(imagen, format='JPEG')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 396):
            for admite_fotos in (False, True):
                page = browser.new_page(viewport={'width': ancho, 'height': 900}, accept_downloads=True)
                page.add_init_script("""localStorage.setItem('eventos_sesion','prueba');
                  window.enviosFoto=[]; window.chats=[];
                  window.open=(url)=>{window.chats.push(url);return null;};
                  navigator.share=async datos=>{window.enviosFoto.push({nombre:datos.files[0].name,bytes:datos.files[0].size,texto:datos.text});};
                  navigator.canShare=()=>%s;""" % str(admite_fotos).lower())
                def api(route):
                    url = route.request.url.split('?')[0]
                    data = {}
                    if url.endswith('/acceso/yo'): data=dict(email='prueba@example.com',opciones=[])
                    elif url.endswith('/acceso'): data=dict(permisos=['ver_invitados','distribuir','configurar_evento'],config=dict(activo=True,canales=['whatsapp','email']),roles_disponibles={})
                    elif url.endswith('/lista'): data=dict(total=1,items=[dict(id=1,nombre='Ana',apellido='',canal='whatsapp',distribucion='PREPARADO',activo=True,nombres_menores=[])])
                    elif url.endswith('/portada.jpg'):
                        route.fulfill(status=200,content_type='image/jpeg',body=imagen.getvalue()); return
                    elif url.endswith('/distribuir'): data=dict(resultados=[dict(id=1,destinatario='Ana',telefono_destino='+5491112345678',estado='PREPARADO',canal='whatsapp',mensaje='Hola Ana',enlace='https://example.com/invitacion',url_canal='https://wa.me/5491112345678?text=Prueba')])
                    route.fulfill(status=200,content_type='application/json',body=json.dumps(data))
                page.route('**/api-vps/**',api)
                page.on('dialog',lambda d: (_ for _ in ()).throw(AssertionError('Dialogo nativo inesperado')))
                page.goto('http://localhost:5179/e/prueba/invitados')
                page.get_by_role('button',name='Reenviar invitacion',exact=True).click()
                popup=page.get_by_role('dialog',name='Enviar invitacion',exact=True)
                expect(popup).to_be_visible()
                expect(popup.locator('img')).to_have_count(0)
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
                    assert foto['nombre']=='invitacion.jpg' and foto['bytes']>0 and 'https://example.com/invitacion' in foto['texto']
                    page.evaluate("() => {navigator.share=async()=>{throw new DOMException('Cancelado','AbortError');};}")
                    popup.get_by_role('button',name='Compartir foto y mensaje',exact=True).click()
                    expect(popup.get_by_text('Compartir cancelado. Podes volver a intentarlo.')).to_be_visible()
                else:
                    with page.expect_download() as descarga:
                        popup.get_by_role('button',name='Descargar foto y abrir chat',exact=True).click()
                    assert descarga.value.suggested_filename=='invitacion.jpg'
                    assert page.evaluate('window.chats[0]').startswith('https://wa.me/')
                page.keyboard.press('Escape')
                expect(popup).to_have_count(0)
                page.close()
        browser.close()
    print('OK: una ventana, una accion principal, foto y enlace, descarga alternativa y cancelacion; escritorio y movil.')

if __name__=='__main__':
    main()
