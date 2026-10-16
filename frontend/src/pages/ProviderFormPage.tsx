import axios from "axios";
import { ArrowLeft, ExternalLink, MailCheck, MapPin, Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { categoryOptions } from "../data/categoriasProveedor";
import { providerTemplates, ProviderTemplateKey } from "../templates/visualTemplates";
import { Proveedor } from "../types/proveedores";

type FieldErrors = Partial<Record<keyof typeof emptyForm | "form", string>>;

type MediaRead = {
  public_url: string;
};

const emptyForm = {
  nombre_comercial: "",
  slug: "",
  cuit: "",
  descripcion: "",
  categorias: [] as string[],
  pais: "Argentina",
  provincia: "",
  localidad: "",
  direccion: "",
  google_maps_url: "",
  google_place_id: "",
  ubicacion_referencia: "",
  whatsapp: "",
  telefono: "",
  email: "",
  web: "",
  instagram: "",
  facebook: "",
  logo_url: "",
  portada_url: "",
  horarios: "",
  template_key: "professional",
  plan: "GRATIS"
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const cuitPattern = /^\d{2}-?\d{8}-?\d$/;

function isHttpUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function isGoogleMapsUrl(value: string) {
  try {
    const url = new URL(value);
    return url.hostname.includes("google.") || url.hostname === "maps.app.goo.gl";
  } catch {
    return false;
  }
}

export function ProviderFormPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [savedProviderSlug, setSavedProviderSlug] = useState<string | null>(null);
  const [tokenAlta, setTokenAlta] = useState<string | null>(null);
  const [confirmationEmail, setConfirmationEmail] = useState("");
  const [resending, setResending] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);
  const [resendError, setResendError] = useState<string | null>(null);
  const [uploadingMedia, setUploadingMedia] = useState<"PORTADA" | "LOGO" | null>(null);

  useEffect(() => {
    if (!slug) return;
    api.get<Proveedor>(`/proveedores/${slug}`).then((response) => {
      const proveedor = response.data;
      setForm({
        nombre_comercial: proveedor.nombre_comercial,
        slug: proveedor.slug,
        cuit: proveedor.cuit ?? "",
        descripcion: proveedor.descripcion ?? "",
        categorias: proveedor.categorias,
        pais: proveedor.pais,
        provincia: proveedor.provincia ?? "",
        localidad: proveedor.localidad ?? "",
        direccion: proveedor.direccion ?? "",
        google_maps_url: proveedor.google_maps_url ?? "",
        google_place_id: proveedor.google_place_id ?? "",
        ubicacion_referencia: proveedor.ubicacion_referencia ?? "",
        whatsapp: proveedor.whatsapp ?? "",
        telefono: proveedor.telefono ?? "",
        email: proveedor.email ?? "",
        web: proveedor.web ?? "",
        instagram: proveedor.instagram ?? "",
        facebook: proveedor.facebook ?? "",
        logo_url: proveedor.logo_url ?? "",
        portada_url: proveedor.portada_url ?? "",
        horarios: proveedor.horarios ?? "",
        template_key: proveedor.template_key ?? "professional",
        plan: proveedor.plan
      });
    });
  }, [slug]);

  const clearError = (key: keyof typeof emptyForm) => {
    setErrors((current) => {
      const next = { ...current };
      delete next[key];
      delete next.form;
      return next;
    });
  };

  const update = (key: keyof typeof form, value: string | string[]) => {
    setForm((current) => ({ ...current, [key]: value }));
    clearError(key);
  };

  const toggleCategory = (category: string) => {
    setForm((current) => {
      const selected = current.categorias.includes(category)
        ? current.categorias.filter((item) => item !== category)
        : [...current.categorias, category];
      return { ...current, categorias: selected };
    });
    clearError("categorias");
  };

  const mapsSearchUrl = () => {
    const query = [form.direccion, form.localidad, form.provincia, form.pais]
      .filter(Boolean)
      .join(", ");
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
      query || form.nombre_comercial || "eventos"
    )}`;
  };

  const validate = () => {
    const nextErrors: FieldErrors = {};

    if (form.nombre_comercial.trim().length < 2) {
      nextErrors.nombre_comercial = "Carga un nombre comercial.";
    }
    if (!form.slug.trim()) {
      nextErrors.slug = "El slug es obligatorio.";
    } else if (!slugPattern.test(form.slug.trim())) {
      nextErrors.slug = "Usa minusculas, numeros y guiones.";
    }
    if (form.cuit.trim() && !cuitPattern.test(form.cuit.trim())) {
      nextErrors.cuit = "Carga un CUIT valido.";
    }
    if (form.categorias.length === 0) {
      nextErrors.categorias = "Selecciona al menos una categoria.";
    }
    if (!form.provincia.trim()) {
      nextErrors.provincia = "Carga la provincia.";
    }
    if (!form.localidad.trim()) {
      nextErrors.localidad = "Carga la localidad.";
    }
    if (!form.direccion.trim()) {
      nextErrors.direccion = "Carga la direccion.";
    }
    if (form.google_maps_url.trim() && !isGoogleMapsUrl(form.google_maps_url.trim())) {
      nextErrors.google_maps_url = "Debe ser un enlace de Google Maps.";
    }
    if (!form.email.trim()) {
      nextErrors.email = "Carga el email para confirmar el alta.";
    } else if (!emailPattern.test(form.email.trim())) {
      nextErrors.email = "Carga un email valido.";
    }
    if (form.web.trim() && !isHttpUrl(form.web.trim())) {
      nextErrors.web = "Carga una URL valida, con http o https.";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const applyServerErrors = (error: unknown) => {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 409) {
        setErrors({ slug: "El slug ya esta en uso." });
        return;
      }

      if (error.response?.status === 503) {
        setErrors({
          form:
            "La base de datos no esta disponible o las credenciales no coinciden. No se pudo guardar todavia."
        });
        return;
      }

      const detail = error.response?.data?.detail;
      if (Array.isArray(detail)) {
        const nextErrors: FieldErrors = {};
        for (const item of detail) {
          const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : undefined;
          if (typeof field === "string" && field in form) {
            nextErrors[field as keyof typeof form] = item.msg ?? "Dato invalido.";
          }
        }
        setErrors(Object.keys(nextErrors).length ? nextErrors : { form: "Revisa los datos marcados." });
        return;
      }

      if (!error.response) {
        setErrors({
          form:
            "No se pudo conectar con el backend. Revisa que la API y PostgreSQL esten funcionando."
        });
        return;
      }
    }

    setErrors({ form: "No se pudo guardar el proveedor. Revisa los datos cargados." });
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors({});

    if (!validate()) return;

    setSaving(true);

    const payload = {
      ...form,
      nombre_comercial: form.nombre_comercial.trim(),
      slug: form.slug.trim(),
      cuit: form.cuit.trim() || null,
      provincia: form.provincia.trim(),
      localidad: form.localidad.trim(),
      direccion: form.direccion.trim(),
      google_maps_url: form.google_maps_url.trim() || null,
      google_place_id: form.google_place_id.trim() || null,
      ubicacion_referencia: form.ubicacion_referencia.trim() || null,
      latitud: null,
      longitud: null,
      email: form.email.trim(),
      web: form.web.trim() || null,
      whatsapp: form.whatsapp.trim() || null,
      telefono: form.telefono.trim() || null,
      instagram: form.instagram.trim() || null,
      facebook: form.facebook.trim() || null,
      logo_url: form.logo_url.trim() || null,
      portada_url: form.portada_url.trim() || null,
      horarios: form.horarios.trim() || null
    };

    const request = slug
      ? api.put<Proveedor>(`/proveedores/${slug}`, payload)
      : api.post<Proveedor>("/proveedores", payload);

    request
      .then((response) => {
        if (slug) {
          navigate(`/p/${response.data.slug}`);
          return;
        }
        setSavedProviderSlug(response.data.slug);
        setTokenAlta((response.data as { token_alta?: string }).token_alta ?? null);
        setConfirmationEmail(response.data.email ?? form.email.trim());
      })
      .catch(applyServerErrors)
      .finally(() => setSaving(false));
  };

  const inputClass = (field: keyof typeof emptyForm) => (errors[field] ? "invalid-field" : undefined);
  const selectedTemplate = providerTemplates[form.template_key as ProviderTemplateKey];

  const uploadMedia = (tipo: "PORTADA" | "LOGO", file: File | undefined) => {
    if (!file || !slug) return;
    const formData = new FormData();
    formData.append("file", file);
    setUploadingMedia(tipo);
    setErrors({});
    api
      .post<MediaRead>(`/media/proveedores/${slug}/${tipo}`, formData)
      .then((response) => {
        update(tipo === "PORTADA" ? "portada_url" : "logo_url", response.data.public_url);
      })
      .catch(() => {
        setErrors({ form: "No se pudo subir la imagen. Usa JPG, PNG o WebP de hasta 5 MB." });
      })
      .finally(() => setUploadingMedia(null));
  };

  const resendConfirmationEmail = () => {
    setResendError(null);
    setResendMessage(null);

    const email = confirmationEmail.trim();
    if (!emailPattern.test(email)) {
      setResendError("Carga un email valido para reenviar.");
      return;
    }
    if (!savedProviderSlug) return;

    setResending(true);
    api
      .post<Proveedor>(`/proveedores/${savedProviderSlug}/reenviar-confirmacion`, {
        email,
        token_alta: tokenAlta
      })
      .then((response) => {
        setConfirmationEmail(response.data.email ?? email);
        setResendMessage("Reenviamos el correo de confirmacion.");
      })
      .catch(() => setResendError("No se pudo reenviar el email. Intenta nuevamente."))
      .finally(() => setResending(false));
  };

  if (savedProviderSlug) {
    return (
      <main className={`providers-page template-live-page ${selectedTemplate.className}`}>
        <section className="confirmation-panel">
          <MailCheck size={36} aria-hidden="true" />
          <p className="eyebrow">Validacion enviada</p>
          <h1>Revisa tu email</h1>
          <p>
            Guardamos el proveedor y enviamos un correo de confirmacion al email indicado.
            Desde ese correo podras validar el negocio y volver a la app.
          </p>
          <label className="confirmation-email-field">
            Email utilizado
            <input
              aria-invalid={Boolean(resendError)}
              className={resendError ? "invalid-field" : undefined}
              value={confirmationEmail}
              onChange={(event) => {
                setConfirmationEmail(event.target.value);
                setResendError(null);
                setResendMessage(null);
              }}
            />
            {resendError && <span className="field-error">{resendError}</span>}
            {resendMessage && <span className="success-inline">{resendMessage}</span>}
          </label>
          <div className="confirmation-actions">
            <button
              className="secondary-button"
              type="button"
              onClick={resendConfirmationEmail}
              disabled={resending}
            >
              <MailCheck size={18} aria-hidden="true" />
              {resending ? "Reenviando..." : "Reenviar mail"}
            </button>
            <button className="secondary-button" type="button" onClick={() => navigate("/")}>
              <ArrowLeft size={18} aria-hidden="true" />
              Volver al inicio
            </button>
            <button
              className="action-button"
              type="button"
              onClick={() => navigate(`/p/${savedProviderSlug}`)}
            >
              Ver pagina publica
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className={`providers-page template-live-page ${selectedTemplate.className}`}>
      <header className="page-header compact-header">
        <div>
          <p className="eyebrow">Mi negocio</p>
          <h1>{slug ? "Editar proveedor" : "Alta de proveedor"}</h1>
        </div>
      </header>

      <form className="provider-form" onSubmit={submit} noValidate>
        <label>
          Nombre comercial
          <input
            aria-invalid={Boolean(errors.nombre_comercial)}
            className={inputClass("nombre_comercial")}
            value={form.nombre_comercial}
            onChange={(event) => update("nombre_comercial", event.target.value)}
          />
          {errors.nombre_comercial && <span className="field-error">{errors.nombre_comercial}</span>}
        </label>
        <label>
          Slug
          <input
            aria-invalid={Boolean(errors.slug)}
            className={inputClass("slug")}
            value={form.slug}
            onChange={(event) => update("slug", event.target.value)}
            placeholder="salon-del-lago"
          />
          {errors.slug && <span className="field-error">{errors.slug}</span>}
        </label>
        <label>
          CUIT
          <input
            aria-invalid={Boolean(errors.cuit)}
            className={inputClass("cuit")}
            value={form.cuit}
            onChange={(event) => update("cuit", event.target.value)}
            placeholder="20-12345678-9"
          />
          {errors.cuit && <span className="field-error">{errors.cuit}</span>}
        </label>
        <label>
          Plan
          <select value={form.plan} onChange={(event) => update("plan", event.target.value)}>
            <option>GRATIS</option>
            <option>PREMIUM</option>
          </select>
        </label>
        <label className="wide">
          Descripcion
          <textarea
            value={form.descripcion}
            onChange={(event) => update("descripcion", event.target.value)}
          />
        </label>
        <section className="media-upload-box wide" aria-label="Imagenes del proveedor">
          <div>
            <div className="field-heading">Imagen de portada</div>
            {form.portada_url ? (
              <img className="media-preview" src={form.portada_url} alt="Portada actual" />
            ) : (
              <p>Sin portada cargada.</p>
            )}
            <label>
              Subir portada
              <input
                accept="image/jpeg,image/png,image/webp"
                disabled={!slug || uploadingMedia === "PORTADA"}
                type="file"
                onChange={(event) => uploadMedia("PORTADA", event.target.files?.[0])}
              />
            </label>
          </div>
          <div>
            <div className="field-heading">Logo</div>
            {form.logo_url ? (
              <img className="logo-preview" src={form.logo_url} alt="Logo actual" />
            ) : (
              <p>Sin logo cargado.</p>
            )}
            <label>
              Subir logo
              <input
                accept="image/jpeg,image/png,image/webp"
                disabled={!slug || uploadingMedia === "LOGO"}
                type="file"
                onChange={(event) => uploadMedia("LOGO", event.target.files?.[0])}
              />
            </label>
          </div>
          {!slug && <p className="form-hint">Primero guarda el proveedor para poder subir imagenes.</p>}
        </section>
        {uploadingMedia && <p className="success-inline wide">Subiendo imagen...</p>}
        <label>
          Horarios
          <input
            value={form.horarios}
            onChange={(event) => update("horarios", event.target.value)}
            placeholder="Lunes a sabado de 9 a 18"
          />
        </label>

        <section className="appearance-picker wide" aria-label="Apariencia del proveedor">
          <div>
            <div className="field-heading">Apariencia</div>
            <label>
              Estilo
              <select
                value={form.template_key}
                onChange={(event) => update("template_key", event.target.value)}
              >
                {Object.entries(providerTemplates).map(([key, template]) => (
                  <option key={key} value={key}>
                    {template.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="template-preview-card">
            <div className="template-preview-swatches">
              {selectedTemplate.swatches.map((color) => (
                <span key={color} style={{ background: color }} />
              ))}
            </div>
            <strong>{selectedTemplate.label}</strong>
            <p>{selectedTemplate.description}</p>
            <span className="preview-link">Vista previa</span>
          </div>
        </section>

        <section
          className={errors.categorias ? "category-picker wide invalid-group" : "category-picker wide"}
          aria-label="Categorias"
        >
          <div className="field-heading">Categorias</div>
          <div className="category-grid">
            {categoryOptions.map((category) => (
              <button
                className={
                  form.categorias.includes(category.slug)
                    ? "category-option selected"
                    : "category-option"
                }
                key={category.slug}
                type="button"
                onClick={() => toggleCategory(category.slug)}
              >
                {category.label}
              </button>
            ))}
          </div>
          {errors.categorias && <span className="field-error">{errors.categorias}</span>}
        </section>

        <label>
          Provincia
          <input
            aria-invalid={Boolean(errors.provincia)}
            className={inputClass("provincia")}
            value={form.provincia}
            onChange={(event) => update("provincia", event.target.value)}
          />
          {errors.provincia && <span className="field-error">{errors.provincia}</span>}
        </label>
        <label>
          Localidad
          <input
            aria-invalid={Boolean(errors.localidad)}
            className={inputClass("localidad")}
            value={form.localidad}
            onChange={(event) => update("localidad", event.target.value)}
          />
          {errors.localidad && <span className="field-error">{errors.localidad}</span>}
        </label>
        <label className="wide">
          Direccion
          <input
            aria-invalid={Boolean(errors.direccion)}
            className={inputClass("direccion")}
            value={form.direccion}
            onChange={(event) => update("direccion", event.target.value)}
          />
          {errors.direccion && <span className="field-error">{errors.direccion}</span>}
        </label>

        <section className="maps-picker wide" aria-label="Ubicacion de Google Maps">
          <div>
            <div className="field-heading">Ubicacion en Google Maps</div>
            <p>
              Si el negocio tiene una ubicacion en Google Maps, podes pegar el enlace compartido
              para mostrarlo en invitaciones y en la pagina publica del proveedor.
            </p>
          </div>
          <a className="secondary-link" href={mapsSearchUrl()} target="_blank" rel="noreferrer">
            <MapPin size={18} aria-hidden="true" />
            Seleccionar en Google Maps
          </a>
        </section>

        <label className="wide">
          Enlace de Google Maps (opcional)
          <input
            aria-invalid={Boolean(errors.google_maps_url)}
            className={inputClass("google_maps_url")}
            value={form.google_maps_url}
            onChange={(event) => update("google_maps_url", event.target.value)}
            placeholder="https://maps.google.com/..."
          />
          {errors.google_maps_url && <span className="field-error">{errors.google_maps_url}</span>}
        </label>
        <label className="wide">
          Referencia de ubicacion
          <input
            value={form.ubicacion_referencia}
            onChange={(event) => update("ubicacion_referencia", event.target.value)}
            placeholder="Frente a la plaza principal"
          />
        </label>

        <label>
          WhatsApp
          <input value={form.whatsapp} onChange={(event) => update("whatsapp", event.target.value)} />
        </label>
        <label>
          Email
          <input
            aria-invalid={Boolean(errors.email)}
            className={inputClass("email")}
            value={form.email}
            onChange={(event) => update("email", event.target.value)}
          />
          {errors.email && <span className="field-error">{errors.email}</span>}
        </label>
        <label>
          Web
          <input
            aria-invalid={Boolean(errors.web)}
            className={inputClass("web")}
            value={form.web}
            onChange={(event) => update("web", event.target.value)}
          />
          {errors.web && <span className="field-error">{errors.web}</span>}
        </label>
        <label>
          Instagram
          <input value={form.instagram} onChange={(event) => update("instagram", event.target.value)} />
        </label>

        {errors.form && <p className="form-error wide">{errors.form}</p>}
        <div className="form-actions provider-submit-actions wide">
          <button className="secondary-button" type="button" onClick={() => navigate("/")}>
            <ArrowLeft size={18} aria-hidden="true" />
            Cancelar
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => navigate(`/p/${slug ?? form.slug}`)}
            disabled={!(slug ?? form.slug)}
          >
            <ExternalLink size={18} aria-hidden="true" />
            Ver pagina
          </button>
          <button className="action-button" type="submit" disabled={saving}>
            <Save size={18} aria-hidden="true" />
            {saving ? "Guardando..." : "Guardar proveedor"}
          </button>
        </div>
      </form>
    </main>
  );
}
