"""Acceso de roles por Google; API simulada sin correos reales."""
import json

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280,396):
            for anterior in (True,False):
                for autorizado in (True,False):
                    llamadas=[]
                    opciones=[dict(path="/e/prueba", token="cuenta-evento", cuenta_id=2)]
                    permisos=["ver_invitados","editar_invitados","distribuir"] if autorizado else []
                    def api(route):
                        url=route.request.url.split('?')[0]
                        llamadas.append(url)
                        if url.endswith('/google-config'):
                            data={'client_id':'prueba.apps.googleusercontent.com'}
                        elif url.endswith('/google') or url.endswith('/yo'):
                            data=dict(token='sesion-google', email='equipo@example.com', usuario_id=2, opciones=opciones)
                        elif url.endswith('/permisos'):
                            data=dict(usuario={'id':2}, puede_editar=False, permisos_invitados=permisos)
                        elif url.endswith('/portal'):
                            data=dict(validado=False, acceso_equipo=True, validacion='email')
                        elif url.endswith('/acceso'):
                            data=dict(permisos=permisos, usuario_id=2, solo_responsable=False, roles_disponibles={}, config=dict(activo=True, canales=['email']))
                        elif '/lista' in url:
                            data=dict(items=[],total=0)
                        else:
                            data=[]
                        route.fulfill(status=200,content_type='application/json',body=json.dumps(data))
                    context=browser.new_context(viewport={'width':ancho,'height':858})
                    context.route('**/api-vps/**',api)
                    context.route('https://accounts.google.com/gsi/client',lambda r:r.fulfill(content_type='application/javascript',body="""
                        window.google={accounts:{id:{initialize(o){window.credencial=o.callback;},renderButton(el){let b=document.createElement('button'); b.textContent='Elegir cuenta de Google'; b.onclick=()=>window.credencial({credential:'google-verificado'}); el.appendChild(b);}}}};
                    """))
                    page=context.new_page()
                    page.goto('http://localhost:5179/e/prueba/'+('i/'+'t'*43 if anterior else 'acceso-equipo'))
                    expect(page.get_by_role('heading',name='Ingresar como Agasajado o Administrador')).to_be_visible()
                    expect(page.get_by_role('button',name='Solicitar codigo por email')).to_have_count(0)
                    expect(page.get_by_role('heading',name='Ingresar y confirmar mi invitacion')).to_have_count(0)
                    page.get_by_role('button',name='Elegir cuenta de Google').click()
                    if autorizado:
                        expect(page).to_have_url('http://localhost:5179/e/prueba/invitados')
                        expect(page.get_by_role('button',name='Agregar invitado individual')).to_be_visible()
                        assert page.evaluate("sessionStorage.getItem('eventos_cuenta_pestana')").find('cuenta-evento')>=0
                    else:
                        expect(page.get_by_role('alert')).to_contain_text('no tiene un rol asignado')
                        expect(page.get_by_role('button',name='Agregar invitado individual')).to_have_count(0)
                    assert not any('/portal/codigo' in u or '/portal/validar' in u for u in llamadas)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    context.close()
        browser.close()
    print('OK: agasajado/administrador por Google sin codigos, enlace anterior y nuevo, cuenta con rol y sin rol, movil y escritorio.')


if __name__=='__main__':
    main()
