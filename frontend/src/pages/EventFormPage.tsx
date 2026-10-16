import { ArrowLeft, Eye, MailCheck, Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { obtenerTokenSesion } from "../api/sesion";
import { fechaLocalAIso } from "../components/EdicionEvento";
import { mensajeDeError } from "../components/EdicionProveedor";
import {
  DatosLugar,
  LUGAR_VACIO,
  lugarParaGuardar,
  SelectorLugar,
  validarLugar
} from "../components/SelectorLugar";
import { eventTemplates, EventTemplateKey } from "../templates/visualTemplates";

type EventoCreado = { slug: string; email_confirmacion: string };

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function generarSlug(texto: string) {
  return (
    texto
      // normalize("NFD") separa letras y acentos para poder quitar los acentos
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
  );
}

export function EventFormPage() {
  const navigate = useNavigate();

  const [templateKey, setTemplateKey] = useState<EventTemplateKey>("classic");
  const [nombre, setNombre] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEditadoAMano, setSlugEditadoAMano] = useState(false);
  const [fecha, setFecha] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [lugar, setLugar] = useState<DatosLugar>(LUGAR_VACIO);
  const [email, setEmail] = useState("");
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [guardando, setGuardando] = useState(false);
  const [reenviando, setReenviando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [emailConfirmacion, setEmailConfirmacion] = useState<string | null>(null);

  const template = eventTemplates[templateKey];

  useEffect(() => {
    if (obtenerTokenSesion()) {
      api
        .get<{ email: string }>("/acceso/yo")
        .then((response) => setEmail((actual) => actual || response.data.email))
        .catch(() => undefined);
    }
  }, []);

  const cambiarNombre = (valor: string) => {
    setNombre(valor);
    if (!slugEditadoAMano) setSlug(generarSlug(valor));
  };

  const validar = () => {
    const nuevos: Record<string, string> = {};
    if (nombre.trim().length < 2) nuevos.nombre = "Carga el nombre del evento.";
    if (!slugPattern.test(slug)) nuevos.slug = "Usa minusculas, numeros y guiones (ej: cumple-de-guada).";
    const problemaLugar = validarLugar(lugar);
    if (problemaLugar) nuevos.lugar = problemaLugar;
    if (!emailPattern.test(email.trim())) {
      nuevos.email = "Carga tu email: ahi te llega el enlace para confirmar el evento.";
    }
    setErrores(nuevos);
    return Object.keys(nuevos).length === 0;
  };

  const guardar = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setAviso(null);
    if (!validar()) return;

    const payload = {
      nombre: nombre.trim(),
      slug,
      descripcion: descripcion.trim() || null,
      fecha_inicio: fechaLocalAIso(fecha),
      ...lugarParaGuardar(lugar),
      template_key: templateKey,
      email: email.trim()
    };

    setGuardando(true);
    api
      .post<EventoCreado>("/eventos", payload)
      .then(({ data }) => {
        setSlug(data.slug);
        setEmailConfirmacion(data.email_confirmacion);
      })
      .catch((error) => {
        if (error?.response?.status === 409) {
          setErrores({ slug: "Ese slug ya esta en uso. Proba con otro." });
          return;
        }
        setErrores({ form: mensajeDeError(error) });
      })
      .finally(() => setGuardando(false));
  };

  const reenviar = () => {
    setReenviando(true);
    setAviso(null);
    api
      .post(`/eventos/${slug}/reenviar-confirmacion`)
      .then(() => setAviso("Reenviamos el mail de confirmacion."))
      .catch(() => setAviso("No se pudo reenviar. Intenta en un momento."))
      .finally(() => setReenviando(false));
  };

  if (emailConfirmacion) {
    return (
      <main className={`providers-page template-live-page ${template.className}`}>
        <section className="confirmation-panel">
          <MailCheck size={36} aria-hidden="true" />
          <p className="eyebrow">Confirmacion enviada</p>
          <h1>Revisa tu email</h1>
          <p>
            Creamos el evento <strong>{nombre}</strong>. Enviamos un
            correo a <strong>{emailConfirmacion}</strong>. El evento no se publica hasta que abras el
            enlace de ese correo: al abrirlo se confirma y entras a su pagina como administrador. El
            enlace vence en 48 horas.
          </p>
          {aviso && <p className="success-inline">{aviso}</p>}
          <div className="confirmation-actions">
            <button className="secondary-button" type="button" onClick={reenviar} disabled={reenviando}>
              <MailCheck size={18} aria-hidden="true" />
              {reenviando ? "Reenviando..." : "Reenviar mail"}
            </button>
            <button className="secondary-button" type="button" onClick={() => navigate("/")}>
              <ArrowLeft size={18} aria-hidden="true" />
              Volver al inicio
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className={`providers-page template-live-page ${template.className}`}>
      <header className="page-header compact-header">
        <div>
          <p className="eyebrow">Evento</p>
          <h1>Crear evento</h1>
        </div>
      </header>

      <form className="provider-form" onSubmit={guardar} noValidate>
        <label>
          Nombre del evento
          <input
            className={errores.nombre ? "invalid-field" : undefined}
            value={nombre}
            onChange={(e) => cambiarNombre(e.target.value)}
            placeholder="Cumple de Ale"
          />
          {errores.nombre && <span className="field-error">{errores.nombre}</span>}
        </label>
        <label>
          Slug (direccion del evento)
          <input
            className={errores.slug ? "invalid-field" : undefined}
            value={slug}
            onChange={(e) => {
              setSlugEditadoAMano(true);
              setSlug(generarSlug(e.target.value) + (e.target.value.endsWith("-") ? "-" : ""));
            }}
            placeholder="cumple-de-ale"
          />
          {errores.slug && <span className="field-error">{errores.slug}</span>}
        </label>
        <label>
          Fecha y hora
          <input type="datetime-local" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </label>
        <div className="wide">
          <div className="field-heading">Lugar del evento</div>
          <SelectorLugar
            valor={lugar}
            alCambiar={(cambios) => {
              setLugar((actual) => ({ ...actual, ...cambios }));
              setErrores((actual) => ({ ...actual, lugar: "" }));
            }}
          />
          {errores.lugar && <span className="field-error">{errores.lugar}</span>}
        </div>

        <label className="wide">
          Descripcion
          <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
        </label>

        <label className="wide">
          Tu email (obligatorio: ahi te llega el enlace para confirmar el evento)
          <input
            className={errores.email ? "invalid-field" : undefined}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="tu@email.com"
          />
          {errores.email && <span className="field-error">{errores.email}</span>}
        </label>

        <section className="appearance-picker wide" aria-label="Apariencia del evento">
          <div>
            <div className="field-heading">Apariencia</div>
            <label>
              Estilo
              <select
                value={templateKey}
                onChange={(event) => setTemplateKey(event.target.value as EventTemplateKey)}
              >
                {Object.entries(eventTemplates).map(([key, item]) => (
                  <option key={key} value={key}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="template-preview-card">
            <div className="template-preview-swatches">
              {template.swatches.map((color) => (
                <span key={color} style={{ background: color }} />
              ))}
            </div>
            <strong>{template.label}</strong>
            <p>{template.description}</p>
            <span className="preview-link">
              <Eye size={14} aria-hidden="true" /> Vista previa
            </span>
          </div>
        </section>

        {errores.form && <p className="form-error wide">{errores.form}</p>}
        <div className="form-actions provider-submit-actions wide">
          <button className="secondary-button" type="button" onClick={() => navigate("/")}>
            <ArrowLeft size={18} aria-hidden="true" />
            Cancelar
          </button>
          <button className="action-button" type="submit" disabled={guardando}>
            <Save size={18} aria-hidden="true" />
            {guardando ? "Creando..." : "Crear evento"}
          </button>
        </div>
      </form>
    </main>
  );
}
