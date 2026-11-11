"""Verificacion del invitado sin Google, con API simulada y sin envios reales."""
import json

from playwright.sync_api import expect, sync_playwright


def main():
    evento = dict(id=1, nombre="Fiesta", slug="prueba", titulo_visual="Nuestra fiesta",
        textos_portada=None, descripcion="Nos encontramos", fecha_inicio=None,
        lugar_tipo="domicilio", direccion="Calle 123", localidad="Rio Gallegos",
        provincia="Santa Cruz", pais="Argentina", latitud=None, longitud=None,
        salon=None, portada_url=None, portada_encuadre=None, template_key="classic",
        tipografia="sistema", colores=dict(fondo="#f4f7f6", texto="#18212f", acento="#245c48"),
        estado="PUBLICADO", confirmado=True, modulos_habilitados=[], galeria=[], limite_galeria=10,
        galeria_config=dict(modo="grilla", filas=2, columnas=2))
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for metodo in ("email","telefono","pin"):
            for ancho in (1280,396):
                solicitudes=[]
                publico=dict(validado=False, validacion=metodo, requiere_pin=metodo=="pin", sin_contacto=False)
                privado=dict(validado=True, validacion=metodo, sesion="verificada", nombre="Juan", apellido="",
                    cantidad_permitida=2, adultos=1, nombres_menores=[], solicitados=1, cupo_aprobado=0,
                    ingresados=0, rsvp="PENDIENTE", aprobacion="PENDIENTE", puede_modificar=True, qr=None)
                def api(route):
                    url=route.request.url
                    data=route.request.post_data_json if route.request.method=="POST" else {}
                    solicitudes.append((url,data))
                    status=200
                    if url.endswith('/portal/codigo'):
                        respuesta={'message':'Codigo enviado al contacto registrado'}
                    elif url.endswith('/portal/validar'):
                        correcto=data.get('pin')=='1234567890' if metodo=='pin' else data.get('codigo')=='123456'
                        status=200 if correcto else 401
                        respuesta=privado if correcto else {'detail':'Codigo incorrecto'}
                    elif url.endswith('/portal/rsvp'):
                        status=200 if data.get('sesion')=='verificada' else 401
                        respuesta={**privado,'rsvp':'CONFIRMADO'} if status==200 else {'detail':'Verifica tu acceso'}
                    elif url.endswith('/portal'):
                        respuesta=privado if data.get('sesion')=='verificada' else publico
                    else:
                        respuesta=evento
                    route.fulfill(status=status,content_type='application/json',body=json.dumps(respuesta))
                context=browser.new_context(viewport={'width':ancho,'height':858})
                context.route('**/api-vps/**',api)
                page=context.new_page()
                url='http://localhost:5179/e/prueba/i/'+'t'*43
                page.goto(url)
                expect(page.get_by_role('heading',name='Nuestra fiesta',exact=True)).to_be_visible()
                expect(page.get_by_role('button',name='Guardar mi respuesta',exact=True)).to_have_count(0)
                expect(page.get_by_text('Hola Juan',exact=False)).to_have_count(0)
                if metodo=='pin':
                    campo=page.get_by_label('PIN personal de mi invitacion')
                else:
                    page.get_by_role('button',name='Solicitar codigo por email' if metodo=='email' else 'Solicitar codigo telefonico').click()
                    campo=page.get_by_label('Codigo temporal')
                campo.fill('000000')
                page.get_by_role('button',name='Ingresar a mi invitacion',exact=True).click()
                expect(page.get_by_role('alert')).to_contain_text('Codigo incorrecto')
                expect(page.get_by_role('button',name='Guardar mi respuesta',exact=True)).to_have_count(0)
                campo.fill('1234567890' if metodo=='pin' else '123456')
                page.get_by_role('button',name='Ingresar a mi invitacion',exact=True).click()
                expect(page.get_by_role('heading',name='Hola Juan',exact=False)).to_be_visible()
                page.get_by_role('button',name='Guardar mi respuesta',exact=True).click()
                expect(page.get_by_text('CONFIRMADO',exact=True)).to_be_visible()
                assert all(datos.get('sesion')=='verificada' for ruta,datos in solicitudes if ruta.endswith('/portal/rsvp'))
                assert not any('/acceso/google' in ruta for ruta,_ in solicitudes)
                pedro=browser.new_context(viewport={'width':ancho,'height':858})
                pedro.route('**/api-vps/**',api)
                copia=pedro.new_page(); copia.goto(url)
                expect(copia.get_by_role('button',name='Guardar mi respuesta',exact=True)).to_have_count(0)
                expect(copia.get_by_text('Si esta invitacion no es para vos',exact=False)).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                pedro.close(); context.close()
        browser.close()
    print('OK: email, telefono y PIN; sin Google; datos privados y RSVP solo tras validar; copia del enlace sin acceso; movil y escritorio.')


if __name__=='__main__':
    main()
