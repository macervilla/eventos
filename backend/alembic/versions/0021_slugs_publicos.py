"""URLs publicas unificadas y unicidad global transaccional."""
from alembic import op
import sqlalchemy as sa

revision = "0021_slugs_publicos"
down_revision = "0020_video_en_vivo"
branch_labels = None
depends_on = None

# Copia deliberada: la migracion no depende de futuras reglas de la aplicacion.
RESERVADOS = (
    "admin", "administracion", "login", "ingresar", "api", "api-vps", "eventos",
    "proveedores", "nuevo", "media", "assets", "rtc", "health", "compartir",
    "acceso", "geografia", "ubicacion", "interno", "docs", "redoc", "openapi-json",
)


def upgrade():
    db = op.get_bind()
    # Bloquea escrituras hasta el commit: no hay ventana entre el backfill y los triggers.
    db.execute(sa.text("LOCK TABLE eventos, proveedores IN SHARE ROW EXCLUSIVE MODE"))
    filas = db.execute(sa.text("""
        SELECT slug, 'evento' AS tipo, id FROM eventos
        UNION ALL SELECT slug, 'proveedor', id FROM proveedores
    """)).all()
    vistos, errores = {}, []
    for slug, tipo, entidad_id in filas:
        if slug in vistos:
            errores.append(f"{slug}: {vistos[slug]} y {tipo} #{entidad_id}")
        vistos[slug] = f"{tipo} #{entidad_id}"
        if slug in RESERVADOS:
            errores.append(f"{slug}: ruta reservada ({tipo} #{entidad_id})")
    if errores:
        raise RuntimeError("Slugs en conflicto; no se modificaron datos: " + "; ".join(errores))
    op.create_table("slugs_publicos",
        sa.Column("slug", sa.String(220), primary_key=True),
        sa.Column("tipo", sa.String(16), nullable=False),
        sa.Column("entidad_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("tipo IN ('evento', 'proveedor')", name="ck_slug_tipo"),
        sa.UniqueConstraint("tipo", "entidad_id", name="uq_slug_entidad"))
    db.execute(sa.text("""
        INSERT INTO slugs_publicos (slug, tipo, entidad_id)
        SELECT slug, 'evento', id FROM eventos
        UNION ALL SELECT slug, 'proveedor', id FROM proveedores
    """))
    reservados = ", ".join("'" + s + "'" for s in RESERVADOS)
    op.execute(f"""
        CREATE FUNCTION mantener_slug_publico() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                DELETE FROM slugs_publicos WHERE slug = OLD.slug;
                RETURN OLD;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF NEW.slug IS DISTINCT FROM OLD.slug THEN
                    RAISE EXCEPTION 'El slug es inmutable' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.slug IN ({reservados}) THEN
                RAISE EXCEPTION 'Slug reservado: %', NEW.slug USING ERRCODE = '23514';
            END IF;
            INSERT INTO slugs_publicos (slug, tipo, entidad_id)
            VALUES (NEW.slug, TG_ARGV[0], NEW.id);
            RETURN NEW;
        END $$;
    """)
    for tabla, tipo in (("eventos", "evento"), ("proveedores", "proveedor")):
        op.execute(f"""CREATE TRIGGER slug_publico_{tabla}
            AFTER INSERT OR UPDATE OR DELETE ON {tabla}
            FOR EACH ROW EXECUTE FUNCTION mantener_slug_publico('{tipo}')""")
    op.execute("""
        CREATE FUNCTION proteger_nombre_evento() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.nombre IS DISTINCT FROM OLD.nombre THEN
                RAISE EXCEPTION 'El nombre del evento es inmutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER nombre_evento_inmutable BEFORE UPDATE ON eventos
            FOR EACH ROW EXECUTE FUNCTION proteger_nombre_evento();
    """)


def downgrade():
    op.execute("DROP TRIGGER nombre_evento_inmutable ON eventos")
    op.execute("DROP FUNCTION proteger_nombre_evento()")
    for tabla in ("eventos", "proveedores"):
        op.execute(f"DROP TRIGGER slug_publico_{tabla} ON {tabla}")
    op.execute("DROP FUNCTION mantener_slug_publico()")
    op.drop_table("slugs_publicos")
