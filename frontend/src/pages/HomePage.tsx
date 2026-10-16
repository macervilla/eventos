import {
  ArrowRight,
  Building2,
  Camera,
  CalendarDays,
  CheckCircle2,
  Image,
  MapPin,
  MessageCircle,
  Music,
  PartyPopper,
  QrCode,
  Sparkles,
  Store,
  Users
} from "lucide-react";
import { Link } from "react-router-dom";

const eventTypes = [
  "Cumpleanos",
  "Casamientos",
  "Eventos deportivos",
  "Te bingo",
  "Fiestas",
  "Otros"
];

const providerCategories = [
  "Salones",
  "DJ",
  "Fotografia",
  "Catering",
  "Decoracion",
  "Animacion",
  "Sonido e iluminacion",
  "Otros"
];

export function HomePage() {
  return (
    <main className="portal portal-redesign">
      <header className="portal-header">
        <Link to="/" className="portal-brand">
          Eventos
        </Link>
        <nav className="portal-nav" aria-label="Navegacion principal">
          <a href="#como-funciona">Como funciona</a>
          <Link to="/proveedores">Proveedores</Link>
          <a href="#planes">Planes</a>
          <Link to="/proveedores/nuevo">Ser proveedor</Link>
          <Link to="/ingresar">Ingresar</Link>
        </nav>
        <Link className="portal-header-cta" to="/eventos/nuevo">
          Crear mi evento
        </Link>
      </header>

      <section className="portal-hero-v2">
        <div className="hero-copy-v2">
          <p className="portal-kicker">Eventos, recuerdos y proveedores cerca</p>
          <h1>Tus eventos. Tus recuerdos. Todo en un solo lugar.</h1>
          <p>
            Crea tu evento, invita a tus personas, comparti fotos y videos y encontra proveedores
            cerca tuyo.
          </p>
          <div className="hero-actions">
            <Link className="primary-link warm-primary" to="/eventos/nuevo">
              <CalendarDays size={20} aria-hidden="true" />
              Crear mi evento
            </Link>
            <Link className="secondary-link warm-secondary" to="/proveedores/nuevo">
              <Store size={20} aria-hidden="true" />
              Publicar mi negocio
            </Link>
          </div>
        </div>

        <div className="product-collage" aria-label="Vista previa del producto">
          <article className="event-preview-card">
            <div className="event-preview-photo" />
            <div>
              <span>Sabado 21:00</span>
              <h2>Cumple de Ale</h2>
              <p>120 invitados · Rio Gallegos</p>
            </div>
          </article>
          <article className="memory-card">
            <Image size={20} aria-hidden="true" />
            <strong>48 recuerdos nuevos</strong>
            <span>Fotos, mensajes y videos en una URL permanente.</span>
          </article>
          <article className="supplier-card">
            <MapPin size={20} aria-hidden="true" />
            <strong>DJ a 2.4 km</strong>
            <span>Proveedor cercano disponible para consultar.</span>
          </article>
          <article className="qr-card">
            <QrCode size={36} aria-hidden="true" />
            <span>Invitacion QR</span>
          </article>
          <article className="guest-card">
            <CheckCircle2 size={20} aria-hidden="true" />
            <strong>Confirmaciones</strong>
            <span>86 asisten · 14 pendientes</span>
          </article>
        </div>
      </section>

      <section id="como-funciona" className="portal-section-v2">
        <div className="section-heading">
          <p className="portal-kicker">Como funciona</p>
          <h2>De la invitacion al recuerdo, sin perder el hilo.</h2>
        </div>
        <div className="steps-grid-v2">
          <article>
            <CalendarDays size={24} aria-hidden="true" />
            <h3>Crear un evento</h3>
            <p>Configura nombre, fecha, ubicacion, portada y modulos activos.</p>
          </article>
          <article>
            <Users size={24} aria-hidden="true" />
            <h3>Compartir e invitar</h3>
            <p>Envia el enlace o QR y administra confirmaciones desde el panel.</p>
          </article>
          <article>
            <Camera size={24} aria-hidden="true" />
            <h3>Guardar recuerdos</h3>
            <p>Fotos, videos y mensajes quedan disponibles aun despues del evento.</p>
          </article>
          <article>
            <MapPin size={24} aria-hidden="true" />
            <h3>Encontrar proveedores cercanos</h3>
            <p>Busca salones, DJ, catering y servicios por localidad o cercania.</p>
          </article>
          <article>
            <Store size={24} aria-hidden="true" />
            <h3>Publicar un negocio</h3>
            <p>Cada proveedor puede tener pagina publica, contacto y ubicacion.</p>
          </article>
        </div>
      </section>

      <section className="portal-section-v2 event-types-section">
        <div className="section-heading">
          <p className="portal-kicker">Tipos de eventos</p>
          <h2>Un espacio para cada tipo de evento.</h2>
        </div>
        <div className="event-type-grid">
          {eventTypes.map((type, index) => (
            <article key={type} className={`event-type-card type-${index + 1}`}>
              <PartyPopper size={22} aria-hidden="true" />
              <span>{type}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="portal-section-v2 providers-showcase">
        <div>
          <p className="portal-kicker">Proveedores</p>
          <h2>Encontra todo para tu evento.</h2>
          <p>
            Proveedores cerca de Rio Gallegos
            <Link to="/proveedores" className="inline-action">
              Cambiar ubicacion
            </Link>
          </p>
        </div>
        <div className="provider-category-grid">
          {providerCategories.map((category) => (
            <Link to="/proveedores" key={category}>
              <Building2 size={18} aria-hidden="true" />
              {category}
            </Link>
          ))}
        </div>
      </section>

      <section className="portal-section-v2 memories-section">
        <div className="memory-visual">
          <div className="photo-strip one" />
          <div className="photo-strip two" />
          <div className="photo-strip three" />
        </div>
        <div>
          <p className="portal-kicker">Recuerdos</p>
          <h2>El evento termina. El recuerdo queda.</h2>
          <p>
            Conserva fotos, videos, mensajes y una URL permanente para volver al evento cuando
            quieras. El espacio cambia de participacion a memoria sin perder su historia.
          </p>
        </div>
      </section>

      <section id="planes" className="portal-section-v2">
        <div className="section-heading">
          <p className="portal-kicker">Planes</p>
          <h2>Empeza simple y crece cuando tu evento lo pida.</h2>
        </div>
        <div className="plans-grid-v2">
          <article>
            <h3>Gratis</h3>
            <ul>
              <li>Crear evento</li>
              <li>URL permanente</li>
              <li>Fotos limitadas</li>
              <li>Confirmaciones</li>
              <li>Publicidad</li>
              <li>Personalizacion basica</li>
            </ul>
          </article>
          <article className="featured-plan">
            <h3>Premium</h3>
            <ul>
              <li>Mas almacenamiento</li>
              <li>Sin publicidad</li>
              <li>Videos</li>
              <li>Mas personalizacion</li>
              <li>Funciones avanzadas</li>
            </ul>
          </article>
        </div>
        <Link className="primary-link warm-primary section-cta" to="/planes">
          Ver planes
        </Link>
      </section>

      <section className="portal-section-v2 supplier-business-section">
        <div>
          <p className="portal-kicker">Para proveedores</p>
          <h2>Tu pagina comercial dentro de la plataforma.</h2>
          <p>
            Publica imagenes, descripcion, servicios, ubicacion, contacto y redes. Tu negocio puede
            aparecer en busquedas por cercania y tener una URL propia como
            <strong> eventos.app/p/salon-del-lago</strong>.
          </p>
          <p className="domain-note">Preparado para futuros dominios como www.salondellago.com.</p>
          <Link className="secondary-link warm-secondary" to="/proveedores/nuevo">
            Publicar mi negocio
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </div>
        <div className="supplier-benefits">
          <span><Sparkles size={18} /> Pagina comercial</span>
          <span><Image size={18} /> Imagenes y galeria</span>
          <span><MapPin size={18} /> Ubicacion</span>
          <span><MessageCircle size={18} /> Contacto</span>
          <span><Music size={18} /> Servicios</span>
          <span><Store size={18} /> Busqueda por cercania</span>
        </div>
      </section>

      <section className="final-cta-v2">
        <p className="portal-kicker">Listo para empezar</p>
        <h2>Crea un evento o publica tu negocio hoy.</h2>
        <div className="hero-actions">
          <Link className="primary-link warm-primary" to="/eventos/nuevo">
            Crear mi evento
          </Link>
          <Link className="secondary-link warm-secondary" to="/proveedores">
            Buscar proveedores
          </Link>
        </div>
      </section>

      <footer className="footer footer-v2">Eventos · Plataforma unica para eventos y proveedores</footer>
    </main>
  );
}
