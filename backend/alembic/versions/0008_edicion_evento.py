"""Identidad Google persistente y presentacion editable del evento."""
import sqlalchemy as sa
from alembic import op

revision = "0008_edicion_evento"
down_revision = "0007_superadministrador"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("google_subject", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_users_google_subject", "users", ["google_subject"])
    op.add_column("eventos", sa.Column("titulo_visual", sa.String(180), nullable=True))
    op.add_column("eventos", sa.Column("colores", sa.JSON(), nullable=True))
    op.execute("""
        CREATE FUNCTION proteger_identidad_evento() RETURNS trigger AS $$
        BEGIN
          IF NEW.nombre IS DISTINCT FROM OLD.nombre OR NEW.slug IS DISTINCT FROM OLD.slug THEN
            RAISE EXCEPTION 'El nombre original y el slug del evento son inmutables';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER evento_identidad_inmutable BEFORE UPDATE ON eventos
        FOR EACH ROW EXECUTE FUNCTION proteger_identidad_evento();
    """)


def downgrade():
    op.execute("DROP TRIGGER evento_identidad_inmutable ON eventos")
    op.execute("DROP FUNCTION proteger_identidad_evento()")
    op.drop_column("eventos", "colores")
    op.drop_column("eventos", "titulo_visual")
    op.drop_constraint("uq_users_google_subject", "users", type_="unique")
    op.drop_column("users", "google_subject")
