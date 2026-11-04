"""Habilitar las galerias existentes que ya tienen imagenes cargadas."""
from alembic import op

revision = "0009_galeria_publica"
down_revision = "0008_edicion_evento"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO evento_modulos (evento_id, modulo, activo, configuracion_json, created_at, updated_at)
        SELECT evento_id, 'galeria', true, '{}'::json, now(), now()
        FROM (SELECT DISTINCT evento_id FROM media
              WHERE evento_id IS NOT NULL AND tipo = 'GALERIA' AND activo = true) existentes
        ON CONFLICT (evento_id, modulo) DO UPDATE SET activo = true, updated_at = now()
    """)


def downgrade():
    # No se revierte la visibilidad elegida por el usuario ni se eliminan imagenes.
    pass
